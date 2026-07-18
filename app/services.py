from datetime import datetime, timedelta

from sqlalchemy.orm import Session, joinedload

from app.models import (
    Customer,
    Diagnosis,
    Part,
    PurchaseOrder,
    PurchaseOrderLine,
    Reception,
    ShopSettings,
    StockMovement,
    Vehicle,
    WorkOrder,
    WorkOrderLine,
)


STATUS_FLOW = [
    "recibido",
    "en_diagnostico",
    "esperando_repuestos",
    "en_reparacion",
    "listo",
    "entregado",
]


def next_code(db: Session, prefix: str, model, field: str = "code") -> str:
    today = datetime.utcnow().strftime("%y%m%d")
    base = f"{prefix}-{today}-"
    last = (
        db.query(model)
        .filter(getattr(model, field).like(f"{base}%"))
        .order_by(model.id.desc())
        .first()
    )
    seq = 1
    if last:
        try:
            seq = int(getattr(last, field).split("-")[-1]) + 1
        except ValueError:
            seq = 1
    return f"{base}{seq:03d}"


def get_settings(db: Session) -> ShopSettings:
    settings = db.query(ShopSettings).first()
    if not settings:
        settings = ShopSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def customer_dict(c: Customer) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "phone": c.phone,
        "email": c.email,
        "id_number": c.id_number,
        "notes": c.notes,
    }


def vehicle_dict(v: Vehicle) -> dict:
    return {
        "id": v.id,
        "customer_id": v.customer_id,
        "plate": v.plate,
        "brand": v.brand,
        "model": v.model,
        "year": v.year,
        "color": v.color,
        "vin": v.vin,
        "notes": v.notes,
        "customer": customer_dict(v.customer) if v.customer else None,
    }


def part_dict(p: Part) -> dict:
    low = p.stock_qty <= p.min_stock
    return {
        "id": p.id,
        "sku": p.sku,
        "name": p.name,
        "brand": p.brand,
        "category": p.category,
        "compatible_with": p.compatible_with,
        "location": p.location,
        "cost_price": p.cost_price,
        "sale_price": p.sale_price,
        "stock_qty": p.stock_qty,
        "min_stock": p.min_stock,
        "unit": p.unit,
        "preferred_supplier_id": p.preferred_supplier_id,
        "preferred_supplier": p.preferred_supplier.name if p.preferred_supplier else None,
        "low_stock": low,
        "active": p.active,
    }


def recalculate_work_order(wo: WorkOrder) -> None:
    wo.parts_total = sum(line.line_total for line in wo.lines)
    wo.labor_total = round((wo.labor_hours or 0) * (wo.labor_rate or 0), 2)
    wo.grand_total = round(wo.parts_total + wo.labor_total, 2)


def reception_dict(r: Reception, full: bool = True) -> dict:
    data = {
        "id": r.id,
        "code": r.code,
        "status": r.status,
        "odometer_km": r.odometer_km,
        "fuel_level": r.fuel_level,
        "customer_complaint": r.customer_complaint,
        "accessories": r.accessories,
        "received_by": r.received_by,
        "promised_at": r.promised_at.isoformat() if r.promised_at else None,
        "customer_accepted": r.customer_accepted,
        "customer_signature_name": r.customer_signature_name,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        "vehicle": vehicle_dict(r.vehicle) if r.vehicle else None,
    }
    if full:
        data["damages"] = [
            {
                "id": d.id,
                "zone": d.zone,
                "severity": d.severity,
                "description": d.description,
                "present_on_arrival": d.present_on_arrival,
            }
            for d in r.damages
        ]
        data["photos"] = [
            {
                "id": p.id,
                "filename": p.filename,
                "url": f"/uploads/{p.filename}",
                "caption": p.caption,
                "zone": p.zone,
            }
            for p in r.photos
        ]
        data["diagnosis"] = (
            {
                "id": r.diagnosis.id,
                "technician": r.diagnosis.technician,
                "symptoms": r.diagnosis.symptoms,
                "findings": r.diagnosis.findings,
                "obd_codes": r.diagnosis.obd_codes,
                "recommended_work": r.diagnosis.recommended_work,
                "estimated_hours": r.diagnosis.estimated_hours,
                "estimated_parts_cost": r.diagnosis.estimated_parts_cost,
                "estimated_labor_cost": r.diagnosis.estimated_labor_cost,
                "priority": r.diagnosis.priority,
            }
            if r.diagnosis
            else None
        )
        data["work_order"] = work_order_dict(r.work_order) if r.work_order else None
    return data


def work_order_dict(wo: WorkOrder) -> dict:
    return {
        "id": wo.id,
        "code": wo.code,
        "status": wo.status,
        "labor_notes": wo.labor_notes,
        "labor_hours": wo.labor_hours,
        "labor_rate": wo.labor_rate,
        "labor_total": wo.labor_total,
        "parts_total": wo.parts_total,
        "grand_total": wo.grand_total,
        "assigned_to": wo.assigned_to,
        "created_at": wo.created_at.isoformat() if wo.created_at else None,
        "lines": [
            {
                "id": line.id,
                "part_id": line.part_id,
                "description": line.description,
                "quantity": line.quantity,
                "unit_price": line.unit_price,
                "line_total": line.line_total,
                "status": line.status,
                "part": part_dict(line.part) if line.part else None,
            }
            for line in wo.lines
        ],
        "reception_id": wo.reception_id,
    }


def ensure_work_order(db: Session, reception: Reception, assigned_to: str = "") -> WorkOrder:
    if reception.work_order:
        return reception.work_order
    settings = get_settings(db)
    wo = WorkOrder(
        reception_id=reception.id,
        code=next_code(db, "OT", WorkOrder),
        status="abierta",
        assigned_to=assigned_to,
        labor_rate=settings.labor_rate,
    )
    db.add(wo)
    db.flush()
    return wo


def apply_stock_change(
    db: Session,
    part: Part,
    quantity: float,
    movement_type: str,
    reference: str = "",
    note: str = "",
    created_by: str = "",
) -> Part:
    part.stock_qty = round((part.stock_qty or 0) + quantity, 2)
    db.add(
        StockMovement(
            part_id=part.id,
            movement_type=movement_type,
            quantity=quantity,
            reference=reference,
            note=note,
            created_by=created_by,
        )
    )
    return part


def reserve_part_for_work_order(
    db: Session,
    wo: WorkOrder,
    part: Part,
    quantity: float,
    user_name: str = "",
) -> WorkOrderLine:
    if part.stock_qty < quantity:
        raise ValueError(
            f"Stock insuficiente de {part.name}. Disponible: {part.stock_qty}. "
            "Solicite el repuesto al proveedor."
        )
    apply_stock_change(
        db,
        part,
        -quantity,
        "salida",
        reference=wo.code,
        note="Reservado para orden de trabajo",
        created_by=user_name,
    )
    line = WorkOrderLine(
        work_order_id=wo.id,
        part_id=part.id,
        description=f"{part.sku} — {part.name}",
        quantity=quantity,
        unit_price=part.sale_price,
        line_total=round(quantity * part.sale_price, 2),
        status="reservado",
    )
    db.add(line)
    db.flush()
    recalculate_work_order(wo)
    return line


def create_purchase_for_part(
    db: Session,
    part: Part,
    quantity: float,
    work_order_id: int | None = None,
    notes: str = "",
) -> PurchaseOrder:
    if not part.preferred_supplier_id:
        raise ValueError("El repuesto no tiene proveedor preferido configurado.")
    po = PurchaseOrder(
        code=next_code(db, "OC", PurchaseOrder),
        supplier_id=part.preferred_supplier_id,
        work_order_id=work_order_id,
        status="solicitado",
        notes=notes or f"Pedido automático por falta de stock: {part.name}",
        total=round(quantity * part.cost_price, 2),
    )
    db.add(po)
    db.flush()
    db.add(
        PurchaseOrderLine(
            purchase_order_id=po.id,
            part_id=part.id,
            quantity=quantity,
            unit_cost=part.cost_price,
            line_total=round(quantity * part.cost_price, 2),
        )
    )
    if work_order_id:
        wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
        if wo:
            db.add(
                WorkOrderLine(
                    work_order_id=wo.id,
                    part_id=part.id,
                    description=f"{part.sku} — {part.name} (pedido a proveedor)",
                    quantity=quantity,
                    unit_price=part.sale_price,
                    line_total=round(quantity * part.sale_price, 2),
                    status="pedido",
                )
            )
            recalculate_work_order(wo)
            reception = db.query(Reception).filter(Reception.id == wo.reception_id).first()
            if reception and reception.status in ("recibido", "en_diagnostico", "en_reparacion"):
                reception.status = "esperando_repuestos"
    return po


def receive_purchase_order(db: Session, po: PurchaseOrder, user_name: str = "") -> PurchaseOrder:
    if po.status == "recibido":
        return po
    for line in po.lines:
        apply_stock_change(
            db,
            line.part,
            line.quantity,
            "entrada",
            reference=po.code,
            note="Entrada por orden de compra",
            created_by=user_name,
        )
        if po.work_order_id:
            wo = db.query(WorkOrder).options(joinedload(WorkOrder.lines)).filter(WorkOrder.id == po.work_order_id).first()
            if wo:
                pending = [
                    l
                    for l in wo.lines
                    if l.part_id == line.part_id and l.status == "pedido"
                ]
                for wl in pending:
                    if line.part.stock_qty >= wl.quantity:
                        apply_stock_change(
                            db,
                            line.part,
                            -wl.quantity,
                            "salida",
                            reference=wo.code,
                            note="Auto-reserva tras llegada de proveedor",
                            created_by=user_name,
                        )
                        wl.status = "reservado"
                if all(l.status in ("reservado", "instalado") for l in wo.lines) or not wo.lines:
                    reception = db.query(Reception).filter(Reception.id == wo.reception_id).first()
                    if reception and reception.status == "esperando_repuestos":
                        reception.status = "en_reparacion"
    po.status = "recibido"
    po.received_at = datetime.utcnow()
    return po


def dashboard_stats(db: Session) -> dict:
    receptions = db.query(Reception).all()
    by_status: dict[str, int] = {}
    for r in receptions:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    low_stock = db.query(Part).filter(Part.active.is_(True)).all()
    low = [part_dict(p) for p in low_stock if p.stock_qty <= p.min_stock]
    open_pos = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.status.in_(["solicitado", "confirmado", "en_camino"]))
        .count()
    )
    today = datetime.utcnow().date()
    today_count = sum(1 for r in receptions if r.created_at and r.created_at.date() == today)
    ready = by_status.get("listo", 0)
    in_shop = sum(
        by_status.get(s, 0)
        for s in ("recibido", "en_diagnostico", "esperando_repuestos", "en_reparacion", "listo")
    )
    return {
        "today_receptions": today_count,
        "in_shop": in_shop,
        "ready_for_delivery": ready,
        "open_purchase_orders": open_pos,
        "low_stock_count": len(low),
        "by_status": by_status,
        "low_stock": low[:12],
        "board": [
            reception_dict(r, full=False)
            for r in sorted(receptions, key=lambda x: x.updated_at or x.created_at, reverse=True)
            if r.status != "entregado"
        ][:40],
    }


def default_promise(hours: int = 24) -> datetime:
    return datetime.utcnow() + timedelta(hours=hours)
