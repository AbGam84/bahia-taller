"""Pro features that put bahía at Tekmetric / Shopmonkey / TallerAlpha level."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session, joinedload

from app.models import (
    Appointment,
    Customer,
    Estimate,
    EstimateLine,
    InspectionCheck,
    Reception,
    ServiceCatalog,
    Vehicle,
    WorkOrder,
)
from app.services import (
    get_settings,
    next_code,
    part_dict,
    reception_dict,
    work_order_dict,
)

DVI_SYSTEMS = [
    ("frenos", "Frenos"),
    ("motor", "Motor"),
    ("suspension", "Suspensión"),
    ("electrico", "Eléctrico"),
    ("llantas", "Llantas / neumáticos"),
    ("fluidos", "Fluidos"),
    ("direccion", "Dirección"),
    ("transmision", "Transmisión"),
    ("luces", "Luces"),
    ("aire", "Aire acondicionado"),
    ("escape", "Escape"),
    ("carroceria", "Carrocería"),
]

def ensure_public_token(reception: Reception) -> str:
    if not reception.public_token:
        reception.public_token = secrets.token_urlsafe(18)
    return reception.public_token


def seed_inspection(db: Session, reception: Reception) -> list[InspectionCheck]:
    if reception.inspection_checks:
        return list(reception.inspection_checks)
    rows = []
    for i, (key, name) in enumerate(DVI_SYSTEMS):
        row = InspectionCheck(
            reception_id=reception.id,
            system_key=key,
            system_name=name,
            status="na",
            sort_order=i,
        )
        db.add(row)
        rows.append(row)
    db.flush()
    return rows


def seed_services(db: Session) -> None:
    """Catálogo vacío a propósito: el taller carga sus propios servicios."""
    return


def inspection_dict(checks: list[InspectionCheck]) -> list[dict]:
    return [
        {
            "id": c.id,
            "system_key": c.system_key,
            "system_name": c.system_name,
            "status": c.status,
            "notes": c.notes,
            "sort_order": c.sort_order,
        }
        for c in sorted(checks, key=lambda x: x.sort_order)
    ]


def estimate_dict(est: Estimate | None) -> dict | None:
    if not est:
        return None
    return {
        "id": est.id,
        "code": est.code,
        "status": est.status,
        "notes": est.notes,
        "labor_total": est.labor_total,
        "parts_total": est.parts_total,
        "grand_total": est.grand_total,
        "customer_message": est.customer_message,
        "decided_at": est.decided_at.isoformat() if est.decided_at else None,
        "created_at": est.created_at.isoformat() if est.created_at else None,
        "lines": [
            {
                "id": line.id,
                "kind": line.kind,
                "description": line.description,
                "quantity": line.quantity,
                "unit_price": line.unit_price,
                "line_total": line.line_total,
                "part_id": line.part_id,
                "recommended": line.recommended,
                "approved": line.approved,
            }
            for line in est.lines
        ],
    }


def enrich_reception(r: Reception) -> dict:
    from app.config import PUBLIC_BASE_URL

    data = reception_dict(r, full=True)
    data["public_token"] = ensure_public_token(r)
    path = f"/t/{data['public_token']}"
    data["public_url"] = f"{PUBLIC_BASE_URL}{path}" if PUBLIC_BASE_URL else path
    data["inspection"] = inspection_dict(list(r.inspection_checks or []))
    data["estimate"] = estimate_dict(r.estimate)
    data["dvi_summary"] = {
        "ok": sum(1 for c in (r.inspection_checks or []) if c.status == "ok"),
        "watch": sum(1 for c in (r.inspection_checks or []) if c.status == "watch"),
        "fail": sum(1 for c in (r.inspection_checks or []) if c.status == "fail"),
        "na": sum(1 for c in (r.inspection_checks or []) if c.status == "na"),
    }
    return data


def build_estimate_from_reception(db: Session, reception: Reception) -> Estimate:
    ensure_public_token(reception)
    if reception.estimate:
        est = reception.estimate
        est.lines.clear()
    else:
        est = Estimate(
            reception_id=reception.id,
            code=next_code(db, "COT", Estimate),
            status="borrador",
        )
        db.add(est)
        db.flush()

    settings = get_settings(db)
    labor_total = 0.0
    parts_total = 0.0

    if reception.diagnosis and reception.diagnosis.recommended_work:
        hours = reception.diagnosis.estimated_hours or 1
        rate = settings.labor_rate
        total = round(hours * rate, 2)
        labor_total += total
        db.add(
            EstimateLine(
                estimate_id=est.id,
                kind="servicio",
                description=reception.diagnosis.recommended_work[:240],
                quantity=hours,
                unit_price=rate,
                line_total=total,
                recommended=True,
                approved=False,
            )
        )
    elif reception.work_order and reception.work_order.labor_hours:
        hours = reception.work_order.labor_hours
        rate = reception.work_order.labor_rate or settings.labor_rate
        total = round(hours * rate, 2)
        labor_total += total
        db.add(
            EstimateLine(
                estimate_id=est.id,
                kind="servicio",
                description=reception.work_order.labor_notes or "Mano de obra",
                quantity=hours,
                unit_price=rate,
                line_total=total,
                recommended=True,
            )
        )

    if reception.work_order:
        for line in reception.work_order.lines:
            parts_total += line.line_total
            db.add(
                EstimateLine(
                    estimate_id=est.id,
                    kind="repuesto",
                    description=line.description,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    line_total=line.line_total,
                    part_id=line.part_id,
                    recommended=True,
                )
            )

    # Fail DVI items without lines become recommended service placeholders
    for check in reception.inspection_checks or []:
        if check.status == "fail":
            desc = f"Atender: {check.system_name}" + (f" — {check.notes}" if check.notes else "")
            if not any(l.description == desc for l in est.lines):
                price = settings.labor_rate
                db.add(
                    EstimateLine(
                        estimate_id=est.id,
                        kind="servicio",
                        description=desc,
                        quantity=1,
                        unit_price=price,
                        line_total=price,
                        recommended=True,
                    )
                )
                labor_total += price

    est.labor_total = round(labor_total, 2)
    est.parts_total = round(parts_total, 2)
    est.grand_total = round(labor_total + parts_total, 2)
    est.status = "enviada"
    est.customer_message = (
        "Estimado cliente: revisamos su vehículo en bahía. "
        "Aquí está la cotización clara. Puede aprobar o rechazar desde su celular."
    )
    est.updated_at = datetime.utcnow()
    db.flush()
    return est


def approve_estimate(db: Session, est: Estimate, approved_line_ids: list[int] | None = None) -> Estimate:
    for line in est.lines:
        if approved_line_ids is None:
            line.approved = True
        else:
            line.approved = line.id in approved_line_ids
    est.status = "aprobada"
    est.decided_at = datetime.utcnow()
    # Keep only approved totals visible
    est.labor_total = round(sum(l.line_total for l in est.lines if l.approved and l.kind == "servicio"), 2)
    est.parts_total = round(sum(l.line_total for l in est.lines if l.approved and l.kind == "repuesto"), 2)
    est.grand_total = round(est.labor_total + est.parts_total, 2)
    reception = est.reception
    if reception and reception.status in ("recibido", "en_diagnostico"):
        reception.status = "en_reparacion"
    return est


def decline_estimate(db: Session, est: Estimate, message: str = "") -> Estimate:
    est.status = "rechazada"
    est.decided_at = datetime.utcnow()
    if message:
        est.notes = (est.notes + "\n" if est.notes else "") + f"Cliente: {message}"
    return est


def owner_analytics(db: Session) -> dict:
    from app.services import dashboard_stats

    base = dashboard_stats(db)
    receptions = db.query(Reception).options(
        joinedload(Reception.work_order).joinedload(WorkOrder.lines).joinedload("part"),
        joinedload(Reception.estimate),
        joinedload(Reception.vehicle),
    ).all()

    closed = [r for r in receptions if r.work_order and r.status == "entregado"]
    revenue = sum((r.work_order.grand_total or 0) for r in closed)
    aro = round(revenue / len(closed), 2) if closed else 0

    today = datetime.utcnow().date()
    today_closed = [
        r for r in closed if r.work_order.closed_at and r.work_order.closed_at.date() == today
    ]
    today_revenue = sum((r.work_order.grand_total or 0) for r in today_closed)

    estimates = [r.estimate for r in receptions if r.estimate]
    sent = [e for e in estimates if e.status in ("enviada", "aprobada", "rechazada")]
    approved = [e for e in estimates if e.status == "aprobada"]
    declined = [e for e in estimates if e.status == "rechazada"]
    conversion = round((len(approved) / len(sent)) * 100, 1) if sent else 0

    parts_cost = 0.0
    parts_sale = 0.0
    for r in receptions:
        if not r.work_order:
            continue
        for line in r.work_order.lines:
            parts_sale += line.line_total or 0
            if line.part:
                parts_cost += (line.part.cost_price or 0) * (line.quantity or 0)
    margin = round(parts_sale - parts_cost, 2)
    margin_pct = round((margin / parts_sale) * 100, 1) if parts_sale else 0

    week_ago = datetime.utcnow() - timedelta(days=7)
    week_rev = sum(
        (r.work_order.grand_total or 0)
        for r in closed
        if r.work_order.closed_at and r.work_order.closed_at >= week_ago
    )

    appointments = (
        db.query(Appointment)
        .filter(Appointment.starts_at >= datetime.utcnow() - timedelta(hours=2))
        .order_by(Appointment.starts_at)
        .limit(12)
        .all()
    )

    base.update(
        {
            "revenue_today": today_revenue,
            "revenue_week": week_rev,
            "revenue_closed": revenue,
            "aro": aro,
            "jobs_closed": len(closed),
            "estimate_sent": len(sent),
            "estimate_approved": len(approved),
            "estimate_declined": len(declined),
            "estimate_conversion_pct": conversion,
            "parts_margin": margin,
            "parts_margin_pct": margin_pct,
            "appointments": [
                {
                    "id": a.id,
                    "customer_name": a.customer_name,
                    "phone": a.phone,
                    "plate": a.plate,
                    "vehicle_info": a.vehicle_info,
                    "reason": a.reason,
                    "starts_at": a.starts_at.isoformat(),
                    "status": a.status,
                }
                for a in appointments
            ],
        }
    )
    return base


def vehicle_history(db: Session, vehicle_id: int) -> list[dict]:
    rows = (
        db.query(Reception)
        .options(
            joinedload(Reception.diagnosis),
            joinedload(Reception.work_order),
            joinedload(Reception.estimate),
        )
        .filter(Reception.vehicle_id == vehicle_id)
        .order_by(Reception.created_at.desc())
        .limit(30)
        .all()
    )
    history = []
    for r in rows:
        history.append(
            {
                "id": r.id,
                "code": r.code,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "complaint": r.customer_complaint,
                "odometer_km": r.odometer_km,
                "work_order_total": r.work_order.grand_total if r.work_order else 0,
                "estimate_status": r.estimate.status if r.estimate else None,
                "findings": r.diagnosis.findings if r.diagnosis else "",
            }
        )
    return history


def public_payload(db: Session, token: str) -> dict | None:
    r = (
        db.query(Reception)
        .options(
            joinedload(Reception.vehicle).joinedload(Vehicle.customer),
            joinedload(Reception.damages),
            joinedload(Reception.photos),
            joinedload(Reception.diagnosis),
            joinedload(Reception.work_order).joinedload(WorkOrder.lines),
            joinedload(Reception.inspection_checks),
            joinedload(Reception.estimate).joinedload(Estimate.lines),
        )
        .filter(Reception.public_token == token)
        .first()
    )
    if not r:
        return None
    settings = get_settings(db)
    v = r.vehicle
    c = v.customer if v else None
    timeline = [
        {"key": "recibido", "label": "Ingresó al patio", "done": True},
        {
            "key": "en_diagnostico",
            "label": "Inspección / diagnóstico",
            "done": r.status
            in ("en_diagnostico", "esperando_repuestos", "en_reparacion", "listo", "entregado")
            or bool(r.diagnosis),
        },
        {
            "key": "cotizacion",
            "label": "Cotización",
            "done": bool(r.estimate) and r.estimate.status != "borrador",
        },
        {
            "key": "aprobada",
            "label": "Aprobación del cliente",
            "done": bool(r.estimate) and r.estimate.status == "aprobada",
        },
        {
            "key": "en_reparacion",
            "label": "En reparación",
            "done": r.status in ("en_reparacion", "listo", "entregado", "esperando_repuestos"),
        },
        {"key": "listo", "label": "Listo para retirar", "done": r.status in ("listo", "entregado")},
        {"key": "entregado", "label": "Entregado", "done": r.status == "entregado"},
    ]
    return {
        "shop": {
            "name": settings.shop_name,
            "slogan": settings.slogan,
            "phone": settings.phone,
            "whatsapp": settings.whatsapp,
            "address": settings.address,
        },
        "code": r.code,
        "status": r.status,
        "plate": v.plate if v else "",
        "vehicle": f"{v.brand} {v.model}" if v else "",
        "year": v.year if v else 0,
        "customer_name": c.name if c else "",
        "complaint": r.customer_complaint,
        "promised_at": r.promised_at.isoformat() if r.promised_at else None,
        "timeline": timeline,
        "inspection": inspection_dict(list(r.inspection_checks or [])),
        "photos": [
            {"url": f"/uploads/{p.filename}", "zone": p.zone, "caption": p.caption} for p in r.photos
        ],
        "estimate": estimate_dict(r.estimate),
        "work_order": {
            "code": r.work_order.code,
            "grand_total": r.work_order.grand_total,
            "payment_status": getattr(r.work_order, "payment_status", "pendiente"),
        }
        if r.work_order
        else None,
    }
