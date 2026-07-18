from __future__ import annotations

import json
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session, joinedload

from app.config import CERTS_DIR
from app.fe_cr import (
    CR_TZ,
    HaciendaClient,
    build_clave,
    build_consecutivo,
    build_fe_xml,
    calc_line,
    calc_summary,
    next_sequence,
    representation_html,
)
from app.models import (
    ElectronicInvoice,
    ElectronicInvoiceLine,
    IssuerProfile,
    Reception,
    Vehicle,
    WorkOrder,
)


def get_issuer(db: Session) -> IssuerProfile:
    issuer = db.query(IssuerProfile).first()
    if not issuer:
        issuer = IssuerProfile()
        db.add(issuer)
        db.commit()
        db.refresh(issuer)
    return issuer


def issuer_dict(i: IssuerProfile) -> dict:
    return {
        "id": i.id,
        "nombre": i.nombre,
        "nombre_comercial": i.nombre_comercial,
        "tipo_id": i.tipo_id,
        "numero_id": i.numero_id,
        "codigo_actividad": i.codigo_actividad,
        "correo": i.correo,
        "telefono": i.telefono,
        "provincia": i.provincia,
        "canton": i.canton,
        "distrito": i.distrito,
        "otras_senas": i.otras_senas,
        "sucursal": i.sucursal,
        "terminal": i.terminal,
        "ambiente": i.ambiente,
        "hacienda_user": i.hacienda_user,
        "has_password": bool(i.hacienda_password),
        "has_cert": bool(i.cert_filename),
        "has_pin": bool(i.pin_cert),
        "cert_filename": i.cert_filename or "",
        "cabys_default_servicio": i.cabys_default_servicio,
        "cabys_default_repuesto": i.cabys_default_repuesto,
    }


def cert_path(issuer: IssuerProfile) -> Path | None:
    if not issuer.cert_filename:
        return None
    path = CERTS_DIR / Path(issuer.cert_filename).name
    return path if path.exists() else None


def readiness(db: Session) -> dict:
    issuer = get_issuer(db)
    checks = {
        "emisor_nombre": bool(issuer.nombre and issuer.numero_id),
        "actividad": bool(issuer.codigo_actividad),
        "atv_user": bool(issuer.hacienda_user),
        "atv_password": bool(issuer.hacienda_password),
        "cert_p12": bool(cert_path(issuer)),
        "cert_pin": bool(issuer.pin_cert),
    }
    ready = all(checks.values())
    missing = [k for k, ok in checks.items() if not ok]
    return {
        "ready": ready,
        "ambiente": issuer.ambiente,
        "checks": checks,
        "missing": missing,
        "message": "Listo para transmitir a Hacienda"
        if ready
        else "Complete emisor ATV + certificado .p12 + PIN para aceptación real",
    }


def invoice_dict(inv: ElectronicInvoice) -> dict:
    return {
        "id": inv.id,
        "clave": inv.clave,
        "numero_consecutivo": inv.numero_consecutivo,
        "tipo_documento": inv.tipo_documento,
        "status": inv.status,
        "work_order_id": inv.work_order_id,
        "reception_id": inv.reception_id,
        "receptor_nombre": inv.receptor_nombre,
        "receptor_tipo_id": inv.receptor_tipo_id,
        "receptor_numero_id": inv.receptor_numero_id,
        "receptor_correo": inv.receptor_correo,
        "condicion_venta": inv.condicion_venta,
        "medio_pago": inv.medio_pago,
        "total_venta": inv.total_venta,
        "total_impuesto": inv.total_impuesto,
        "total_comprobante": inv.total_comprobante,
        "hacienda_status": inv.hacienda_status,
        "issued_at": inv.issued_at.isoformat() if inv.issued_at else None,
        "has_xml": bool(inv.xml_content),
        "lines": [
            {
                "id": ln.id,
                "detalle": ln.detalle,
                "cabys": ln.cabys,
                "cantidad": ln.cantidad,
                "precio_unitario": ln.precio_unitario,
                "tarifa_codigo": ln.tarifa_codigo,
                "impuesto_monto": ln.impuesto_monto,
                "monto_total_linea": ln.monto_total_linea,
                "es_servicio": ln.es_servicio,
            }
            for ln in inv.lines
        ],
    }


def _doc_payload(issuer: IssuerProfile, inv: ElectronicInvoice) -> dict:
    lineas = []
    for ln in inv.lines:
        calc = calc_line(
            quantity=Decimal(str(ln.cantidad)),
            unit_price=Decimal(str(ln.precio_unitario)),
            discount=Decimal(str(ln.monto_descuento or 0)),
            tarifa_codigo=ln.tarifa_codigo or "08",
        )
        lineas.append(
            {
                **calc,
                "detalle": ln.detalle,
                "cabys": ln.cabys,
                "unidad": ln.unidad,
                "es_servicio": ln.es_servicio,
            }
        )
    resumen = calc_summary(lineas)
    issued = inv.issued_at.replace(tzinfo=CR_TZ) if inv.issued_at.tzinfo is None else inv.issued_at
    return {
        "clave": inv.clave,
        "tipo_documento": inv.tipo_documento,
        "codigo_actividad": issuer.codigo_actividad,
        "numero_consecutivo": inv.numero_consecutivo,
        "fecha_emision": issued.isoformat(),
        "proveedor_sistemas": "Katire",
        "emisor": {
            "nombre": issuer.nombre,
            "nombre_comercial": issuer.nombre_comercial,
            "tipo_id": issuer.tipo_id,
            "numero_id": issuer.numero_id,
            "correo": issuer.correo,
            "telefono": issuer.telefono,
            "provincia": issuer.provincia,
            "canton": issuer.canton,
            "distrito": issuer.distrito,
            "otras_senas": issuer.otras_senas,
        },
        "receptor": {
            "nombre": inv.receptor_nombre,
            "tipo_id": inv.receptor_tipo_id,
            "numero_id": inv.receptor_numero_id,
            "correo": inv.receptor_correo,
        }
        if inv.tipo_documento != "04"
        else None,
        "condicion_venta": inv.condicion_venta,
        "medio_pago": [x.strip() for x in (inv.medio_pago or "01").split(",") if x.strip()],
        "lineas": lineas,
        "resumen": resumen,
        "moneda": inv.moneda,
        "es_servicio_mayormente": any(ln.es_servicio for ln in inv.lines),
    }


def issue_from_work_order(
    db: Session,
    work_order_id: int,
    *,
    tipo_documento: str = "01",
    condicion_venta: str = "01",
    medio_pago: str = "01",
    tarifa_codigo: str = "08",
) -> ElectronicInvoice:
    issuer = get_issuer(db)
    if not issuer.nombre or not issuer.numero_id or not issuer.codigo_actividad:
        raise ValueError("Complete el emisor Hacienda en Facturación → Configuración ATV")

    wo = (
        db.query(WorkOrder)
        .options(
            joinedload(WorkOrder.lines),
            joinedload(WorkOrder.reception)
            .joinedload(Reception.vehicle)
            .joinedload(Vehicle.customer),
        )
        .filter(WorkOrder.id == work_order_id)
        .first()
    )
    if not wo:
        raise ValueError("Orden de trabajo no encontrada")

    reception = wo.reception
    customer = reception.vehicle.customer if reception and reception.vehicle else None

    seq = next_sequence(db, tipo_documento, issuer.sucursal, issuer.terminal)
    consecutivo = build_consecutivo(issuer.sucursal, issuer.terminal, tipo_documento, seq)
    issued_at = datetime.now(CR_TZ)
    clave = build_clave(
        issued_at=issued_at,
        emisor_id=issuer.numero_id,
        consecutivo=consecutivo,
        situation="1",
    )

    inv = ElectronicInvoice(
        clave=clave,
        numero_consecutivo=consecutivo,
        tipo_documento=tipo_documento,
        status="borrador",
        work_order_id=wo.id,
        reception_id=reception.id if reception else None,
        receptor_nombre=(customer.name if customer else "Consumidor final"),
        receptor_tipo_id="01",
        receptor_numero_id=(customer.id_number if customer and customer.id_number else "000000000"),
        receptor_correo=(customer.email if customer else ""),
        condicion_venta=condicion_venta,
        medio_pago=medio_pago,
        issued_at=issued_at.replace(tzinfo=None),
    )
    db.add(inv)
    db.flush()

    # Mano de obra
    if wo.labor_total and wo.labor_total > 0:
        hours = wo.labor_hours or 1
        unit = (wo.labor_total / hours) if hours else wo.labor_total
        calc = calc_line(
            quantity=Decimal(str(hours)),
            unit_price=Decimal(str(unit)),
            tarifa_codigo=tarifa_codigo,
        )
        db.add(
            ElectronicInvoiceLine(
                invoice_id=inv.id,
                detalle=(wo.labor_notes or "Mano de obra / servicio de taller")[:200],
                cabys=issuer.cabys_default_servicio,
                cantidad=calc["cantidad"],
                unidad="Sp",
                precio_unitario=calc["precio_unitario"],
                monto_descuento=0,
                tarifa_codigo=tarifa_codigo,
                tarifa=calc["tarifa"],
                subtotal=calc["subtotal"],
                impuesto_monto=calc["impuesto_monto"],
                monto_total_linea=calc["monto_total_linea"],
                es_servicio=True,
            )
        )

    for line in wo.lines:
        calc = calc_line(
            quantity=Decimal(str(line.quantity or 1)),
            unit_price=Decimal(str(line.unit_price or 0)),
            tarifa_codigo=tarifa_codigo,
        )
        db.add(
            ElectronicInvoiceLine(
                invoice_id=inv.id,
                detalle=line.description[:200],
                cabys=issuer.cabys_default_repuesto,
                cantidad=calc["cantidad"],
                unidad="Unid",
                precio_unitario=calc["precio_unitario"],
                monto_descuento=0,
                tarifa_codigo=tarifa_codigo,
                tarifa=calc["tarifa"],
                subtotal=calc["subtotal"],
                impuesto_monto=calc["impuesto_monto"],
                monto_total_linea=calc["monto_total_linea"],
                es_servicio=False,
            )
        )

    db.flush()
    db.refresh(inv)
    payload = _doc_payload(issuer, inv)
    inv.xml_content = build_fe_xml(payload)
    inv.total_venta = payload["resumen"]["total_venta_neta"]
    inv.total_impuesto = payload["resumen"]["total_impuesto"]
    inv.total_comprobante = payload["resumen"]["total_comprobante"]
    inv.status = "xml_listo"
    db.commit()
    db.refresh(inv)
    return inv


def rebuild_xml(db: Session, invoice_id: int) -> ElectronicInvoice:
    inv = (
        db.query(ElectronicInvoice)
        .options(joinedload(ElectronicInvoice.lines))
        .filter(ElectronicInvoice.id == invoice_id)
        .first()
    )
    if not inv:
        raise ValueError("Factura no encontrada")
    issuer = get_issuer(db)
    payload = _doc_payload(issuer, inv)
    inv.xml_content = build_fe_xml(payload)
    inv.total_venta = payload["resumen"]["total_venta_neta"]
    inv.total_impuesto = payload["resumen"]["total_impuesto"]
    inv.total_comprobante = payload["resumen"]["total_comprobante"]
    inv.status = "xml_listo"
    db.commit()
    db.refresh(inv)
    return inv


def _extract_ind_estado(status_payload: dict) -> str:
    data = status_payload.get("data") or {}
    if not isinstance(data, dict):
        return ""
    return str(
        data.get("ind-estado")
        or data.get("ind_estado")
        or data.get("estado")
        or ""
    ).strip()


def _apply_hacienda_ind(inv: ElectronicInvoice, ind: str) -> None:
    if not ind:
        return
    inv.hacienda_status = ind
    low = ind.lower()
    if "acept" in low:
        inv.status = "aceptado"
    elif "rechaz" in low:
        inv.status = "rechazado"
    elif "proces" in low or "recib" in low:
        inv.status = "enviado"


def sign_invoice(db: Session, invoice_id: int) -> ElectronicInvoice:
    from app.fe_signer import sign_fe_xml

    inv = (
        db.query(ElectronicInvoice)
        .options(joinedload(ElectronicInvoice.lines))
        .filter(ElectronicInvoice.id == invoice_id)
        .first()
    )
    if not inv:
        raise ValueError("Factura no encontrada")
    issuer = get_issuer(db)
    path = cert_path(issuer)
    if not path:
        raise ValueError("Suba el certificado digital .p12 en Facturación")
    if not issuer.pin_cert:
        raise ValueError("Configure el PIN del certificado .p12")
    if not inv.xml_content or "Signature" not in inv.xml_content:
        if not inv.xml_content:
            rebuild_xml(db, invoice_id)
            db.refresh(inv)
        # Si ya estaba firmado, no re-firmar encima
        if "Signature" not in inv.xml_content:
            inv.xml_content = sign_fe_xml(inv.xml_content, path, issuer.pin_cert)
            inv.status = "firmado"
            inv.hacienda_status = "firmado_local"
            db.commit()
            db.refresh(inv)
    return inv


def poll_hacienda_status(
    db: Session,
    invoice_id: int,
    *,
    attempts: int = 10,
    wait_seconds: float = 2.0,
) -> dict:
    inv = db.query(ElectronicInvoice).filter(ElectronicInvoice.id == invoice_id).first()
    if not inv:
        raise ValueError("Factura no encontrada")
    issuer = get_issuer(db)
    if not issuer.hacienda_user or not issuer.hacienda_password:
        raise ValueError("Configure usuario y clave ATV")
    client = HaciendaClient(issuer.ambiente)
    client.authenticate(issuer.hacienda_user, issuer.hacienda_password)
    last = {}
    ind = ""
    for i in range(max(1, attempts)):
        last = client.get_status(inv.clave)
        ind = _extract_ind_estado(last)
        _apply_hacienda_ind(inv, ind)
        inv.hacienda_response = json.dumps(
            {"consulta": last, "intento": i + 1, "ind_estado": ind},
            ensure_ascii=False,
        )
        db.commit()
        if inv.status in ("aceptado", "rechazado"):
            break
        if i < attempts - 1:
            time.sleep(wait_seconds)
    db.refresh(inv)
    return {
        "ok": inv.status == "aceptado",
        "ind_estado": ind or inv.hacienda_status,
        "status": inv.status,
        "invoice": invoice_dict(inv),
        "consulta": last,
        "message": (
            "Hacienda aceptó el comprobante"
            if inv.status == "aceptado"
            else "Hacienda rechazó el comprobante"
            if inv.status == "rechazado"
            else f"Estado Hacienda: {ind or inv.hacienda_status or 'en proceso'}"
        ),
    }


def send_to_hacienda(db: Session, invoice_id: int, *, wait_acceptance: bool = True) -> dict:
    inv = (
        db.query(ElectronicInvoice)
        .options(joinedload(ElectronicInvoice.lines))
        .filter(ElectronicInvoice.id == invoice_id)
        .first()
    )
    if not inv:
        raise ValueError("Factura no encontrada")
    issuer = get_issuer(db)
    if not issuer.hacienda_user or not issuer.hacienda_password:
        raise ValueError("Configure usuario y clave ATV de Hacienda en Facturación")
    if not issuer.nombre or not issuer.numero_id:
        raise ValueError("Complete nombre y cédula del emisor")
    if not inv.xml_content:
        rebuild_xml(db, invoice_id)
        db.refresh(inv)

    # Firma XAdES obligatoria antes de transmitir
    if "Signature" not in (inv.xml_content or ""):
        try:
            inv = sign_invoice(db, invoice_id)
        except Exception as exc:
            inv.hacienda_status = "pendiente_firma"
            inv.status = "xml_listo"
            inv.hacienda_response = json.dumps({"error_firma": str(exc)}, ensure_ascii=False)
            db.commit()
            return {
                "ok": False,
                "needs_signature": True,
                "message": f"No se pudo firmar: {exc}",
                "invoice": invoice_dict(inv),
            }

    client = HaciendaClient(issuer.ambiente)
    client.authenticate(issuer.hacienda_user, issuer.hacienda_password)
    issued = inv.issued_at
    fecha = issued.replace(tzinfo=CR_TZ).isoformat() if issued.tzinfo is None else issued.isoformat()
    result = client.send_document(
        clave=inv.clave,
        fecha=fecha,
        emisor_tipo=issuer.tipo_id,
        emisor_numero="".join(ch for ch in issuer.numero_id if ch.isdigit()),
        xml_signed=inv.xml_content,
        receptor_tipo=inv.receptor_tipo_id if inv.tipo_documento != "04" else None,
        receptor_numero="".join(ch for ch in (inv.receptor_numero_id or "") if ch.isdigit())
        if inv.tipo_documento != "04"
        else None,
    )
    inv.hacienda_response = json.dumps({"envio": result}, ensure_ascii=False)
    if not result.get("ok"):
        inv.status = "error"
        inv.hacienda_status = f"http_{result.get('status_code')}"
        db.commit()
        return {
            "ok": False,
            "result": result,
            "invoice": invoice_dict(inv),
            "message": f"Hacienda no recibió el XML (HTTP {result.get('status_code')})",
        }

    inv.status = "enviado"
    inv.hacienda_status = "recibido"
    db.commit()

    if wait_acceptance:
        polled = poll_hacienda_status(db, invoice_id, attempts=12, wait_seconds=2.0)
        return {
            "ok": polled["ok"],
            "result": result,
            "invoice": polled["invoice"],
            "ind_estado": polled["ind_estado"],
            "message": polled["message"],
            "consulta": polled.get("consulta"),
        }

    db.refresh(inv)
    return {
        "ok": True,
        "result": result,
        "invoice": invoice_dict(inv),
        "message": "Enviado a Hacienda. Consulte el estado en unos segundos.",
    }


def issue_and_send(
    db: Session,
    work_order_id: int,
    *,
    tipo_documento: str = "01",
    condicion_venta: str = "01",
    medio_pago: str = "01",
    tarifa_codigo: str = "08",
) -> dict:
    inv = issue_from_work_order(
        db,
        work_order_id,
        tipo_documento=tipo_documento,
        condicion_venta=condicion_venta,
        medio_pago=medio_pago,
        tarifa_codigo=tarifa_codigo,
    )
    sent = send_to_hacienda(db, inv.id, wait_acceptance=True)
    sent["issued"] = True
    return sent


def html_for_invoice(db: Session, invoice_id: int) -> str:
    inv = (
        db.query(ElectronicInvoice)
        .options(joinedload(ElectronicInvoice.lines))
        .filter(ElectronicInvoice.id == invoice_id)
        .first()
    )
    if not inv:
        raise ValueError("Factura no encontrada")
    issuer = get_issuer(db)
    return representation_html(_doc_payload(issuer, inv))
