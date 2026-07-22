"""
Katire — Facturación Electrónica Costa Rica
Estructura alineada a comprobantes electrónicos Hacienda v4.4
(clave 50, consecutivo 20, XML FacturaElectronica / TiqueteElectronico).
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from xml.dom import minidom

import httpx
from sqlalchemy.orm import Session

# --- Tarifas IVA Costa Rica (códigos tarifa frecuentes v4.4) ---
IVA_RATES = {
    "01": ("Exento", Decimal("0")),
    "02": ("Reducida 1%", Decimal("1")),
    "03": ("Reducida 2%", Decimal("2")),
    "04": ("Reducida 4%", Decimal("4")),
    "05": ("Transitorio 0%", Decimal("0")),
    "06": ("Transitorio 4%", Decimal("4")),
    "07": ("Transitorio 8%", Decimal("8")),
    "08": ("General 13%", Decimal("13")),
}

DOC_TYPES = {
    "01": "Factura Electrónica",
    "02": "Nota de Débito Electrónica",
    "03": "Nota de Crédito Electrónica",
    "04": "Tiquete Electrónico",
    "08": "Factura Electrónica de Compra",
    "09": "Factura Electrónica de Exportación",
    "10": "Recibo Electrónico de Pago",
}

ID_TYPES = {
    "01": "Cédula Física",
    "02": "Cédula Jurídica",
    "03": "DIMEX",
    "04": "NITE",
    "05": "Extranjero No Domiciliado",
}

CONDICION_VENTA = {
    "01": "Contado",
    "02": "Crédito",
    "03": "Consignación",
    "04": "Apartado",
    "05": "Arrendamiento con opción de compra",
    "06": "Arrendamiento en función financiera",
    "07": "Cobro a favor de un tercero",
    "08": "Servicios prestados al Estado",
    "09": "Pago de servicios prestado al Estado",
    "10": "Venta a crédito en IVA hasta 90 días",
    "11": "Pago de contado",
    "12": "Otros",
}

MEDIO_PAGO = {
    "01": "Efectivo",
    "02": "Tarjeta",
    "03": "Cheque",
    "04": "Transferencia / depósito",
    "05": "Recaudado por terceros",
    "06": "SINPE Móvil",
    "07": "Plataforma digital",
    "99": "Otros",
}

NS_FE = "https://cdn.comprobanteselectronicos.go.cr/xml-schemas/v4.4/facturaElectronica"
NS_TE = "https://cdn.comprobanteselectronicos.go.cr/xml-schemas/v4.4/tiqueteElectronico"
NS_NC = "https://cdn.comprobanteselectronicos.go.cr/xml-schemas/v4.4/notaCreditoElectronica"

CR_TZ = timezone(timedelta(hours=-6))


def money(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def pad_digits(value: str | int, length: int) -> str:
    digits = "".join(ch for ch in str(value) if ch.isalnum())
    return digits.zfill(length)[-length:]


def build_consecutivo(
    sucursal: str,
    terminal: str,
    doc_type: str,
    sequence: int,
) -> str:
    """20 posiciones: sucursal(3) + terminal(5) + tipo(2) + consecutivo(10)."""
    return (
        pad_digits(sucursal, 3)
        + pad_digits(terminal, 5)
        + pad_digits(doc_type, 2)
        + pad_digits(sequence, 10)
    )


def build_clave(
    *,
    issued_at: datetime,
    emisor_id: str,
    consecutivo: str,
    situation: str = "1",
    security_code: str | None = None,
) -> str:
    """
    Clave de 50 posiciones (Hacienda):
    506 + DD + MM + YY + cédula(12) + consecutivo(20) + situación(1) + seguridad(8)
    """
    local = issued_at.astimezone(CR_TZ)
    security = security_code or pad_digits(secrets.randbelow(10**8), 8)
    return (
        "506"
        + local.strftime("%d")
        + local.strftime("%m")
        + local.strftime("%y")
        + pad_digits(emisor_id, 12)
        + pad_digits(consecutivo, 20)
        + str(situation)[0]
        + pad_digits(security, 8)
    )


def calc_line(
    *,
    quantity: Decimal,
    unit_price: Decimal,
    discount: Decimal = Decimal("0"),
    tarifa_codigo: str = "08",
) -> dict:
    qty = money(quantity)
    price = money(unit_price)
    disc = money(discount)
    total = money(qty * price)
    subtotal = money(total - disc)
    rate = IVA_RATES.get(tarifa_codigo, IVA_RATES["08"])[1]
    tax = money(subtotal * rate / Decimal("100"))
    net = money(subtotal + tax)
    return {
        "cantidad": float(qty),
        "precio_unitario": float(price),
        "monto_total": float(total),
        "monto_descuento": float(disc),
        "subtotal": float(subtotal),
        "impuesto_monto": float(tax),
        "impuesto_neto": float(tax),
        "monto_total_linea": float(net),
        "tarifa_codigo": tarifa_codigo,
        "tarifa": float(rate),
    }


def calc_summary(lines: list[dict]) -> dict:
    total_venta = money(sum(Decimal(str(l["monto_total"])) for l in lines))
    total_desc = money(sum(Decimal(str(l.get("monto_descuento", 0))) for l in lines))
    total_venta_neta = money(sum(Decimal(str(l["subtotal"])) for l in lines))
    total_impuesto = money(sum(Decimal(str(l["impuesto_monto"])) for l in lines))
    total_comprobante = money(total_venta_neta + total_impuesto)
    return {
        "total_venta": float(total_venta),
        "total_descuentos": float(total_desc),
        "total_venta_neta": float(total_venta_neta),
        "total_impuesto": float(total_impuesto),
        "total_comprobante": float(total_comprobante),
    }


def _el(parent, tag: str, text: str | None = None, **attrs):
    node = ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items() if v is not None})
    if text is not None:
        node.text = str(text)
    return node


def build_fe_xml(doc: dict) -> str:
    """Genera XML FacturaElectronica / TiqueteElectronico v4.4 (sin firma digital)."""
    doc_type = doc.get("tipo_documento", "01")
    if doc_type == "04":
        ns = NS_TE
        root_name = "TiqueteElectronico"
    elif doc_type == "03":
        ns = NS_NC
        root_name = "NotaCreditoElectronica"
    else:
        ns = NS_FE
        root_name = "FacturaElectronica"

    ET.register_namespace("", ns)
    root = ET.Element(f"{{{ns}}}{root_name}")
    _el(root, "Clave", doc["clave"])
    _el(root, "ProveedorSistemas", doc.get("proveedor_sistemas", "Katire"))
    _el(root, "CodigoActividadEmisor", doc["codigo_actividad"])
    _el(root, "NumeroConsecutivo", doc["numero_consecutivo"])
    _el(root, "FechaEmision", doc["fecha_emision"])

    emisor = _el(root, "Emisor")
    _el(emisor, "Nombre", doc["emisor"]["nombre"])
    ident = _el(emisor, "Identificacion")
    _el(ident, "Tipo", doc["emisor"]["tipo_id"])
    _el(ident, "Numero", doc["emisor"]["numero_id"])
    if doc["emisor"].get("nombre_comercial"):
        _el(emisor, "NombreComercial", doc["emisor"]["nombre_comercial"])
    loc = _el(emisor, "Ubicacion")
    _el(loc, "Provincia", doc["emisor"].get("provincia", "5"))
    _el(loc, "Canton", doc["emisor"].get("canton", "01"))
    _el(loc, "Distrito", doc["emisor"].get("distrito", "01"))
    _el(loc, "OtrasSenas", doc["emisor"].get("otras_senas", "Costa Rica"))
    tel = _el(emisor, "Telefono")
    _el(tel, "CodigoPais", "506")
    _el(tel, "NumTelefono", "".join(ch for ch in doc["emisor"].get("telefono", "60000000") if ch.isdigit()) or "60000000")
    _el(emisor, "CorreoElectronico", doc["emisor"].get("correo", "facturas@katire.cr"))

    if doc.get("receptor") and doc_type != "04":
        receptor = _el(root, "Receptor")
        _el(receptor, "Nombre", doc["receptor"]["nombre"])
        rident = _el(receptor, "Identificacion")
        _el(rident, "Tipo", doc["receptor"]["tipo_id"])
        _el(rident, "Numero", doc["receptor"]["numero_id"])
        if doc["receptor"].get("correo"):
            _el(receptor, "CorreoElectronico", doc["receptor"]["correo"])

    _el(root, "CondicionVenta", doc.get("condicion_venta", "01"))
    if doc.get("plazo_credito"):
        _el(root, "PlazoCredito", str(doc["plazo_credito"]))
    for mp in doc.get("medio_pago", ["01"]):
        _el(root, "MedioPago", mp)

    detalle = _el(root, "DetalleServicio")
    for i, line in enumerate(doc["lineas"], start=1):
        linea = _el(detalle, "LineaDetalle")
        _el(linea, "NumeroLinea", str(i))
        if line.get("cabys"):
            _el(linea, "CodigoCABYS", line["cabys"])
        _el(linea, "Cantidad", f"{line['cantidad']:.3f}")
        _el(linea, "UnidadMedida", line.get("unidad", "Sp" if line.get("es_servicio") else "Unid"))
        _el(linea, "Detalle", line["detalle"][:200])
        _el(linea, "PrecioUnitario", f"{line['precio_unitario']:.5f}")
        _el(linea, "MontoTotal", f"{line['monto_total']:.5f}")
        if line.get("monto_descuento"):
            desc = _el(linea, "Descuento")
            _el(desc, "MontoDescuento", f"{line['monto_descuento']:.5f}")
            _el(desc, "NaturalezaDescuento", line.get("naturaleza_descuento", "Descuento comercial"))
        _el(linea, "SubTotal", f"{line['subtotal']:.5f}")
        _el(linea, "BaseImponible", f"{line['subtotal']:.5f}")
        if line.get("impuesto_monto", 0) > 0 or line.get("tarifa_codigo") == "01":
            imp = _el(linea, "Impuesto")
            _el(imp, "Codigo", "01")
            _el(imp, "CodigoTarifaIVA", line.get("tarifa_codigo", "08"))
            _el(imp, "Tarifa", f"{line.get('tarifa', 13):.2f}")
            _el(imp, "Monto", f"{line['impuesto_monto']:.5f}")
        _el(linea, "ImpuestoNeto", f"{line.get('impuesto_neto', line.get('impuesto_monto', 0)):.5f}")
        _el(linea, "MontoTotalLinea", f"{line['monto_total_linea']:.5f}")

    resumen = _el(root, "ResumenFactura")
    s = doc["resumen"]
    moneda_node = _el(resumen, "CodigoTipoMoneda")
    _el(moneda_node, "CodigoMoneda", doc.get("moneda", "CRC"))
    _el(moneda_node, "TipoCambio", "1.00000")
    serv = f"{s['total_venta_neta']:.5f}" if doc.get("es_servicio_mayormente", True) else "0.00000"
    merc = "0.00000" if doc.get("es_servicio_mayormente", True) else f"{s['total_venta_neta']:.5f}"
    _el(resumen, "TotalServGravados", serv)
    _el(resumen, "TotalServExentos", "0.00000")
    _el(resumen, "TotalMercanciasGravadas", merc)
    _el(resumen, "TotalMercanciasExentas", "0.00000")
    _el(resumen, "TotalGravado", f"{s['total_venta_neta']:.5f}")
    _el(resumen, "TotalExento", "0.00000")
    _el(resumen, "TotalVenta", f"{s['total_venta']:.5f}")
    _el(resumen, "TotalDescuentos", f"{s['total_descuentos']:.5f}")
    _el(resumen, "TotalVentaNeta", f"{s['total_venta_neta']:.5f}")
    _el(resumen, "TotalImpuesto", f"{s['total_impuesto']:.5f}")
    _el(resumen, "TotalComprobante", f"{s['total_comprobante']:.5f}")

    rough = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(rough)
    pretty = parsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")
    # strip extra XML declaration duplicates
    lines = [ln for ln in pretty.splitlines() if ln.strip()]
    if lines and lines[0].startswith("<?xml"):
        return "\n".join(lines)
    return '<?xml version="1.0" encoding="utf-8"?>\n' + "\n".join(lines)


class HaciendaClient:
    """Cliente API recepción comprobantes electrónicos Hacienda CR."""

    def __init__(self, environment: str = "sandbox"):
        self.environment = environment if environment in ("sandbox", "production") else "sandbox"
        if self.environment == "production":
            self.token_url = (
                "https://idp.comprobanteselectronicos.go.cr/auth/realms/rut/"
                "protocol/openid-connect/token"
            )
            self.api_base = "https://api.comprobanteselectronicos.go.cr/recepcion/v1"
            self.client_id = "api-prod"
        else:
            self.token_url = (
                "https://idp.comprobanteselectronicos.go.cr/auth/realms/rut-stag/"
                "protocol/openid-connect/token"
            )
            self.api_base = "https://api.comprobanteselectronicos.go.cr/recepcion-sandbox/v1"
            self.client_id = "api-stag"
        self._token: str | None = None
        self._token_exp: datetime | None = None

    def authenticate(self, username: str, password: str) -> dict:
        data = {
            "grant_type": "password",
            "client_id": self.client_id,
            "username": username,
            "password": password,
        }
        with httpx.Client(timeout=40.0) as client:
            res = client.post(self.token_url, data=data)
            payload = res.json() if res.content else {}
            if res.status_code >= 400:
                raise RuntimeError(payload.get("error_description") or payload.get("error") or res.text)
            self._token = payload["access_token"]
            self._token_exp = datetime.utcnow() + timedelta(seconds=int(payload.get("expires_in", 300)) - 30)
            return {"ok": True, "expires_in": payload.get("expires_in"), "environment": self.environment}

    def _auth_headers(self) -> dict:
        if not self._token:
            raise RuntimeError("Debe autenticarse con Hacienda primero")
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def send_document(
        self,
        *,
        clave: str,
        fecha: str,
        emisor_tipo: str,
        emisor_numero: str,
        xml_signed: str,
        receptor_tipo: str | None = None,
        receptor_numero: str | None = None,
        callback_url: str | None = None,
    ) -> dict:
        body: dict[str, Any] = {
            "clave": clave,
            "fecha": fecha,
            "emisor": {"tipoIdentificacion": emisor_tipo, "numeroIdentificacion": emisor_numero},
            "comprobanteXml": base64.b64encode(xml_signed.encode("utf-8")).decode("ascii"),
        }
        if receptor_tipo and receptor_numero:
            body["receptor"] = {
                "tipoIdentificacion": receptor_tipo,
                "numeroIdentificacion": receptor_numero,
            }
        if callback_url:
            body["callbackUrl"] = callback_url
        with httpx.Client(timeout=60.0) as client:
            res = client.post(f"{self.api_base}/recepcion", headers=self._auth_headers(), json=body)
            text = res.text
            try:
                data = res.json()
            except Exception:
                data = {"raw": text}
            return {"status_code": res.status_code, "ok": res.status_code in (200, 202), "data": data}

    def get_status(self, clave: str) -> dict:
        with httpx.Client(timeout=40.0) as client:
            res = client.get(f"{self.api_base}/recepcion/{clave}", headers=self._auth_headers())
            try:
                data = res.json()
            except Exception:
                data = {"raw": res.text}
            return {"status_code": res.status_code, "data": data}


def next_sequence(db: Session, doc_type: str, sucursal: str, terminal: str) -> int:
    from app.models import InvoiceSequence

    row = (
        db.query(InvoiceSequence)
        .filter(
            InvoiceSequence.doc_type == doc_type,
            InvoiceSequence.sucursal == sucursal,
            InvoiceSequence.terminal == terminal,
        )
        .first()
    )
    if not row:
        row = InvoiceSequence(doc_type=doc_type, sucursal=sucursal, terminal=terminal, last_number=0)
        db.add(row)
        db.flush()
    row.last_number += 1
    db.flush()
    return row.last_number


def representation_html(doc: dict, brand: str = "Katire") -> str:
    s = doc["resumen"]
    lines_html = "".join(
        f"<tr><td>{i}</td><td>{l['detalle']}</td><td>{l['cantidad']}</td>"
        f"<td class='r'>{l['precio_unitario']:,.2f}</td><td class='r'>{l['monto_total_linea']:,.2f}</td></tr>"
        for i, l in enumerate(doc["lineas"], start=1)
    )
    return f"""<!doctype html><html><head><meta charset="utf-8"/>
<title>{doc['clave']}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;600&display=swap');
body{{font-family:'DM Sans',sans-serif;margin:0;padding:32px;background:#f6f3ee;color:#14110f}}
.mark{{font-family:Syne,sans-serif;font-size:42px;letter-spacing:-0.06em;margin:0}}
.mark span{{background:linear-gradient(120deg,#ff4d2e,#ffb347 45%,#1ec9a7);-webkit-background-clip:text;color:transparent}}
.card{{background:#fff;border:1px solid #e5ddd2;border-radius:18px;padding:22px;margin-top:16px}}
table{{width:100%;border-collapse:collapse;margin-top:12px;font-size:13px}}
th,td{{border-bottom:1px solid #ece4da;padding:8px;text-align:left}}
.r{{text-align:right}}
.muted{{color:#6d645c}}
.big{{font-family:Syne,sans-serif;font-size:28px}}
</style></head><body>
<p class="mark">Ka<span>tire</span></p>
<p style="font-family:Syne,sans-serif;font-size:18px;letter-spacing:-0.03em;margin:6px 0 0">De la llave al XML.</p>
<p class="muted">Autorespuesto · WhatsApp 8870-8123 · Hacienda CR v4.4 · {DOC_TYPES.get(doc.get('tipo_documento','01'),'')}</p>
<div class="card">
<strong>{doc['emisor']['nombre']}</strong><br/>
<span class="muted">ID {doc['emisor']['numero_id']} · Actividad {doc['codigo_actividad']}</span><br/>
<span class="muted">Clave: {doc['clave']}</span><br/>
<span class="muted">Consecutivo: {doc['numero_consecutivo']}</span>
</div>
<div class="card">
<strong>Receptor:</strong> {doc.get('receptor',{}).get('nombre','Consumidor final')}<br/>
<span class="muted">{doc.get('receptor',{}).get('numero_id','')}</span>
<table><thead><tr><th>#</th><th>Detalle</th><th>Cant.</th><th class="r">P.Unit</th><th class="r">Total</th></tr></thead>
<tbody>{lines_html}</tbody></table>
<p class="r muted">Subtotal ₡{s['total_venta_neta']:,.2f} · IVA ₡{s['total_impuesto']:,.2f}</p>
<p class="r big">Total ₡{s['total_comprobante']:,.2f}</p>
</div>
<p class="muted">Representación gráfica Katire. El XML es el documento fiscal válido ante Hacienda.</p>
</body></html>"""
