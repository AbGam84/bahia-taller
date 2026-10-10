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
    Part,
    Reception,
    ServiceCatalog,
    Supplier,
    Vehicle,
    WorkOrder,
    WorkOrderLine,
)
from app.services import (
    get_settings,
    next_code,
    part_dict,
    reception_dict,
    vehicle_dict,
    work_order_dict,
)

DVI_SYSTEMS = [
    ("frente", "Frente / parachoques"),
    ("luces", "Luces"),
    ("capot", "Capó"),
    ("motor", "Motor"),
    ("fluidos", "Fluidos"),
    ("parabrisas", "Parabrisas"),
    ("techo", "Techo"),
    ("aire", "Aire acondicionado"),
    ("interior", "Interior / cabina"),
    ("direccion", "Dirección"),
    ("electrico", "Eléctrico"),
    ("transmision", "Transmisión"),
    ("suspension", "Suspensión"),
    ("frenos", "Frenos"),
    ("llantas", "Llantas / neumáticos"),
    ("lateral_izq", "Lateral izquierdo"),
    ("lateral_der", "Lateral derecho"),
    ("escape", "Escape"),
    ("trasera", "Trasera / maletero"),
    ("carroceria", "Carrocería general"),
]


def ensure_public_token(reception: Reception) -> str:
    if not reception.public_token:
        reception.public_token = secrets.token_urlsafe(18)
    return reception.public_token


def seed_inspection(db: Session, reception: Reception) -> list[InspectionCheck]:
    """Crea o completa el checklist del croqui (todas las piezas)."""
    existing = {c.system_key: c for c in (reception.inspection_checks or [])}
    rows = list(existing.values())
    for i, (key, name) in enumerate(DVI_SYSTEMS):
        if key in existing:
            existing[key].system_name = name
            existing[key].sort_order = i
            continue
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
    return sorted(rows, key=lambda x: x.sort_order or 0)


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


def owner_analytics(db: Session, tenant_id: int | None = None) -> dict:
    from app.services import dashboard_stats

    base = dashboard_stats(db, tenant_id=tenant_id)
    rq = db.query(Reception).options(
        joinedload(Reception.work_order).joinedload(WorkOrder.lines).joinedload(WorkOrderLine.part),
        joinedload(Reception.estimate),
        joinedload(Reception.vehicle),
    )
    if tenant_id:
        rq = rq.filter(Reception.tenant_id == tenant_id)
    receptions = rq.all()

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

    aq = db.query(Appointment).filter(Appointment.starts_at >= datetime.utcnow() - timedelta(hours=2))
    if tenant_id:
        aq = aq.filter(Appointment.tenant_id == tenant_id)
    appointments = aq.order_by(Appointment.starts_at).limit(12).all()

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


def _score_part_match(p: Part, brand: str, model: str, plate: str) -> int:
    blob = f"{p.name} {p.brand} {p.compatible_with} {p.category}".lower()
    score = 0
    for t in [brand, model, plate]:
        t = (t or "").strip().lower()
        if t and t in blob:
            score += 1
    return score


def parts_reference_by_plate(
    db: Session,
    tenant_id: int,
    plate: str,
    brand_hint: str = "",
    model_hint: str = "",
    year_hint: str = "",
) -> dict:
    """Historial de repuestos en OTs de este vehículo + sugerencias de bodega."""
    plate_norm = (plate or "").upper().strip()
    empty = {
        "plate": plate_norm,
        "found_vehicle": False,
        "vehicle": None,
        "visits_count": 0,
        "history_parts": [],
        "suggested_parts": [],
    }
    if len(plate_norm.replace("-", "")) < 3:
        return empty

    vehicle = (
        db.query(Vehicle)
        .options(joinedload(Vehicle.customer))
        .join(Customer)
        .filter(Customer.tenant_id == tenant_id, Vehicle.plate == plate_norm)
        .first()
    )
    if not vehicle:
        compact = plate_norm.replace("-", "").replace(" ", "")
        vehicle = (
            db.query(Vehicle)
            .options(joinedload(Vehicle.customer))
            .join(Customer)
            .filter(
                Customer.tenant_id == tenant_id,
                Vehicle.plate.ilike(compact),
            )
            .first()
        )

    brand = (vehicle.brand if vehicle else brand_hint or "").strip()
    model = (vehicle.model if vehicle else model_hint or "").strip()
    year_from_hint = ""
    if year_hint and str(year_hint).isdigit():
        year_from_hint = str(int(year_hint))

    registry_vehicle: dict | None = None
    if not vehicle:
        hints_complete = bool(brand_hint.strip() and model_hint.strip() and year_from_hint)
        if not hints_complete:
            from app.cr_registry_client import lookup_vehicle_by_plate

            reg = lookup_vehicle_by_plate(plate_norm)
            if reg.get("ok") and reg.get("found"):
                registry_vehicle = reg
                if not brand:
                    brand = (reg.get("brand") or "").strip()
                if not model:
                    model = (reg.get("model") or reg.get("model_full") or "").strip()
                if not year_from_hint and reg.get("year"):
                    year_from_hint = str(reg.get("year"))

    history_parts: list[dict] = []
    visits_count = 0
    if vehicle:
        visits_count = (
            db.query(Reception)
            .filter(Reception.vehicle_id == vehicle.id, Reception.tenant_id == tenant_id)
            .count()
        )
        rows = (
            db.query(WorkOrderLine, Reception, Part)
            .join(WorkOrder, WorkOrderLine.work_order_id == WorkOrder.id)
            .join(Reception, WorkOrder.reception_id == Reception.id)
            .outerjoin(Part, WorkOrderLine.part_id == Part.id)
            .filter(Reception.vehicle_id == vehicle.id, Reception.tenant_id == tenant_id)
            .order_by(Reception.created_at.desc())
            .limit(250)
            .all()
        )
        agg: dict[str, dict] = {}
        for line, rec, part in rows:
            desc = (line.description or "").strip()
            if part:
                key = f"p{part.id}"
                name = part.name
                sku = part.sku
                part_id = part.id
                stock_qty = part.stock_qty
                sale_price = line.unit_price or part.sale_price
            else:
                if not desc or desc.lower() in ("repuesto", "pieza"):
                    continue
                key = f"d:{desc.lower()}"
                name = desc
                sku = ""
                part_id = None
                stock_qty = None
                sale_price = line.unit_price
            bucket = agg.get(key)
            used_at = rec.created_at.isoformat() if rec.created_at else None
            if not bucket:
                agg[key] = {
                    "part_id": part_id,
                    "sku": sku,
                    "name": name,
                    "times_used": 1,
                    "last_used_at": used_at,
                    "last_reception_code": rec.code,
                    "last_quantity": line.quantity,
                    "stock_qty": stock_qty,
                    "sale_price": sale_price,
                }
            else:
                bucket["times_used"] += 1
        history_parts = sorted(
            agg.values(),
            key=lambda x: (-x["times_used"], x.get("last_used_at") or ""),
        )[:25]

    parts = (
        db.query(Part)
        .options(joinedload(Part.preferred_supplier))
        .filter(Part.active.is_(True), Part.tenant_id == tenant_id)
        .order_by(Part.name)
        .limit(400)
        .all()
    )
    suggested: list[dict] = []
    history_ids = {h["part_id"] for h in history_parts if h.get("part_id")}
    for p in parts:
        score = _score_part_match(p, brand, model, plate_norm)
        if p.id in history_ids:
            score += 2
        if not brand and not model:
            continue
        if score <= 0:
            continue
        item = part_dict(p)
        item["match_score"] = score
        item["source"] = "bodega"
        suggested.append(item)
    suggested.sort(key=lambda x: (-x["match_score"], x["name"]))
    suggested = suggested[:20]

    result = dict(empty)
    result["plate"] = plate_norm
    result["found_vehicle"] = vehicle is not None
    result["vehicle"] = vehicle_dict(vehicle) if vehicle else None
    result["visits_count"] = visits_count
    result["history_parts"] = history_parts
    result["suggested_parts"] = suggested
    from app.oem_network import vehicle_identity_payload

    vdict = result["vehicle"]
    y = 0
    if year_from_hint:
        y = int(year_from_hint)
    elif year_hint and str(year_hint).isdigit():
        y = int(year_hint)
    elif vdict and vdict.get("year"):
        y = int(vdict.get("year") or 0)
    else:
        y = 0
    result["registry_vehicle"] = registry_vehicle
    result["cr_registry"] = registry_vehicle
    from app.cr_registry_client import plate_lookup_enabled, registry_configured

    result["cr_registry_available"] = plate_lookup_enabled()
    result["cr_registry_live"] = registry_configured()
    result["vehicle_identity"] = vehicle_identity_payload(
        plate_norm,
        vehicle=vdict,
        brand=brand,
        model=model,
        year=y or year_hint or year_from_hint,
        registered=vehicle is not None,
        registry=registry_vehicle,
    )
    return result


def _score_warehouse_part(p: Part, q: str, brand: str, model: str) -> int:
    blob = f"{p.name} {p.sku} {p.brand} {p.compatible_with} {p.category}".lower()
    score = _score_part_match(p, brand, model, "")
    for term in [t for t in [q, brand, model] if t and t.strip()]:
        if term.lower() in blob:
            score += 2
    if q and q.lower() in blob:
        score += 1
    return score


def parts_consulta(
    db: Session,
    tenant_id: int,
    q: str,
    plate: str = "",
    brand: str = "",
    model: str = "",
    year: str = "",
    vin: str = "",
) -> dict:
    """Unifica bodega, historial del vehículo y repuesteras externas."""
    from app.part_shops import (
        build_search_link,
        build_whatsapp_order,
        ensure_default_shops,
        shop_dict,
    )

    ensure_default_shops(db, tenant_id)
    settings = get_settings(db, tenant_id)
    shop_label = settings.shop_name or "el taller"

    search_q = (q or "").strip()
    plate_norm = (plate or "").upper().strip()
    brand = (brand or "").strip()
    model = (model or "").strip()

    plate_ref = None
    if plate_norm or brand or model:
        plate_ref = parts_reference_by_plate(
            db, tenant_id, plate_norm, brand, model, (year or "").strip()
        )

    vehicle = plate_ref.get("vehicle") if plate_ref else None
    if vehicle:
        brand = brand or (vehicle.get("brand") or "")
        model = model or (vehicle.get("model") or "")
        if not (year or "").strip() and vehicle.get("year"):
            year = str(vehicle.get("year"))
    if plate_ref:
        vi = plate_ref.get("vehicle_identity") or {}
        brand = brand or (vi.get("brand") or "").strip()
        model = model or (vi.get("model") or "").strip()
        if not (year or "").strip() and vi.get("year"):
            year = str(vi.get("year"))
        if not (vin or "").strip():
            reg = plate_ref.get("registry_vehicle") or {}
            vin = (vin or vi.get("vin") or reg.get("vin") or "").strip()

    veh_label_parts = [p for p in [plate_norm, brand, model, (year or "").strip()] if p]
    vehicle_label = " ".join(veh_label_parts)

    warehouse: list[dict] = []
    parts = (
        db.query(Part)
        .options(joinedload(Part.preferred_supplier))
        .filter(Part.active.is_(True), Part.tenant_id == tenant_id)
        .order_by(Part.name)
        .limit(500)
        .all()
    )
    sq_lower = search_q.lower()
    for p in parts:
        score = _score_warehouse_part(p, search_q, brand, model)
        blob = f"{p.name} {p.sku} {p.compatible_with} {p.category} {p.brand}".lower()
        if sq_lower and sq_lower not in blob and score <= 0:
            continue
        if not sq_lower and (brand or model):
            b = brand.lower()
            m = model.lower()
            veh_match = (b and b in blob) or (m and m in blob) or score > 0
            if not veh_match and not plate_norm:
                continue
            if not veh_match and plate_norm and score <= 0:
                continue
        item = part_dict(p)
        item["match_score"] = score
        warehouse.append(item)
    warehouse.sort(key=lambda x: (-x["match_score"], x["name"]))
    warehouse = warehouse[:35]

    history_parts = (plate_ref or {}).get("history_parts") or []
    if search_q and history_parts:
        sq = search_q.lower()
        history_parts = [h for h in history_parts if sq in (h.get("name") or "").lower()] or history_parts[:8]

    shops_rows = (
        db.query(Supplier)
        .filter(Supplier.active.is_(True), Supplier.kind == "tienda", Supplier.tenant_id == tenant_id)
        .order_by(Supplier.name)
        .all()
    )
    shops = []
    for s in shops_rows:
        item = shop_dict(s)
        item["search_link"] = build_search_link(s, search_q, vehicle_label)
        item["whatsapp_link"] = build_whatsapp_order(
            s, search_q or "repuesto", vehicle_label, from_shop=shop_label
        )
        shops.append(item)

    dossier = None
    if plate_norm:
        from app.oem_network import vehicle_technical_dossier

        dossier = vehicle_technical_dossier(
            db,
            tenant_id,
            plate_norm,
            brand,
            model,
            (year or "").strip(),
            search_q,
            vin_hint=(vin or "").strip(),
        )

    return {
        "query": search_q,
        "plate": plate_norm,
        "brand": brand,
        "model": model,
        "year": (year or "").strip(),
        "vehicle_label": vehicle_label,
        "found_vehicle": bool(plate_ref and plate_ref.get("found_vehicle")),
        "vehicle": vehicle,
        "visits_count": (plate_ref or {}).get("visits_count") or 0,
        "history_parts": history_parts[:25],
        "warehouse": warehouse,
        "shops": shops,
        "ficha_oem": dossier,
    }


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
    # Avance por estado real: si el patio ya pasó de etapa sin cotizar,
    # no dejamos el timeline trabado en "Cotización / Aprobación".
    advanced_past_quote = r.status in (
        "esperando_repuestos",
        "en_reparacion",
        "listo",
        "entregado",
    )
    has_estimate = bool(r.estimate)
    estimate_sent = has_estimate and r.estimate.status != "borrador"
    estimate_approved = has_estimate and r.estimate.status == "aprobada"
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
            "label": "Cotización" if has_estimate or not advanced_past_quote else "Cotización (omitida)",
            "done": estimate_sent or advanced_past_quote,
        },
        {
            "key": "aprobada",
            "label": "Aprobación del cliente"
            if has_estimate or not advanced_past_quote
            else "Aprobación (omitida)",
            "done": estimate_approved or advanced_past_quote,
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
