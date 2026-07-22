import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated

import aiofiles
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload

from app.auth import create_access_token, get_current_user, verify_password
from app.database import UPLOADS_DIR, Base, engine, get_db, migrate_schema
from app.pro import (
    approve_estimate,
    build_estimate_from_reception,
    decline_estimate,
    enrich_reception,
    ensure_public_token,
    owner_analytics,
    public_payload,
    seed_inspection,
    vehicle_history,
)
from app.models import (
    AllyJob,
    AllyJobEvent,
    Appointment,
    Customer,
    DamageItem,
    Diagnosis,
    Estimate,
    Part,
    PurchaseOrder,
    PurchaseOrderLine,
    Reception,
    ReceptionPhoto,
    ServiceCatalog,
    Supplier,
    User,
    Vehicle,
    WorkOrder,
    WorkOrderLine,
)
from app.schemas import (
    AllyJobIn,
    AllyJobUpdateIn,
    CustomerIn,
    DiagnosisIn,
    LoginIn,
    PartIn,
    PurchaseOrderIn,
    ReceptionIn,
    SettingsIn,
    StatusUpdate,
    StockAdjustIn,
    SupplierIn,
    VehicleIn,
    WorkOrderLineIn,
    WorkOrderUpdate,
)
from app.seed import seed_if_empty
from app.services import (
    create_purchase_for_part,
    customer_dict,
    dashboard_stats,
    default_promise,
    ensure_work_order,
    get_settings,
    next_code,
    part_dict,
    receive_purchase_order,
    reception_dict,
    recalculate_work_order,
    reserve_part_for_work_order,
    vehicle_dict,
    work_order_dict,
)

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"

app = FastAPI(
    title="Katire",
    description="Katire — patio del taller + facturación electrónica Hacienda Costa Rica v4.4",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    migrate_schema()
    db = next(get_db())
    try:
        # Si el seed falla, el patio queda vacío: mejor tumbar el arranque que fingir que sirve.
        seed_if_empty(db)
    finally:
        db.close()


# ---------- Auth ----------
@app.post("/api/auth/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username, User.active.is_(True)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    token = create_access_token({"sub": user.username, "role": user.role})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "name": user.name, "username": user.username, "role": user.role},
    }


@app.get("/api/auth/me")
def me(user: Annotated[User, Depends(get_current_user)]):
    return {"id": user.id, "name": user.name, "username": user.username, "role": user.role}


# ---------- Settings / Dashboard ----------
@app.get("/api/settings")
def settings_get(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = get_settings(db)
    return {
        "shop_name": s.shop_name,
        "slogan": s.slogan,
        "phone": s.phone,
        "whatsapp": s.whatsapp,
        "address": s.address,
        "labor_rate": s.labor_rate,
        "currency": s.currency,
        "sinpe_phone": getattr(s, "sinpe_phone", None) or s.whatsapp or s.phone or "",
        "sinpe_name": getattr(s, "sinpe_name", None) or s.shop_name or "",
    }


@app.put("/api/settings")
def settings_put(payload: SettingsIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role not in ("admin", "recepcion", "mecanico"):
        raise HTTPException(status_code=403, detail="Sin permiso para editar la configuración")
    s = get_settings(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    db.commit()
    return settings_get(db, user)


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return owner_analytics(db)


@app.post("/api/payments/sinpe-link")
def payments_sinpe_link(payload: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Cierre en colones: WhatsApp SINPE + referencia OT/FE (prueba accionable)."""
    from app.sinpe_pay import create_sinpe_link

    wo_id = payload.get("work_order_id")
    inv_id = payload.get("invoice_id")
    result = create_sinpe_link(
        db,
        work_order_id=int(wo_id) if wo_id not in (None, "") else None,
        invoice_id=int(inv_id) if inv_id not in (None, "") else None,
        mark_sent=bool(payload.get("mark_sent", True)),
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "No se pudo generar cobro SINPE")
    return result


@app.get("/api/payments/cierre-proof", response_class=HTMLResponse)
def payments_cierre_proof(
    work_order_id: int | None = None,
    invoice_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Prueba imprimible del cierre de cobro (SINPE + estado + FE)."""
    from app.sinpe_pay import cierre_proof_html, create_sinpe_link

    result = create_sinpe_link(
        db,
        work_order_id=work_order_id,
        invoice_id=invoice_id,
        mark_sent=False,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "Sin datos de cierre")
    return HTMLResponse(cierre_proof_html(result.get("proof") or result))


@app.post("/api/work-orders/{work_order_id}/mark-paid")
def work_order_mark_paid(work_order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    wo.payment_status = "pagado"
    db.commit()
    return {
        "ok": True,
        "id": wo.id,
        "code": wo.code,
        "payment_status": wo.payment_status,
        "promise": "Cierre en colones. Con prueba.",
    }


# ---------- Customers / Vehicles ----------
@app.get("/api/customers")
def customers_list(q: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(Customer)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Customer.name.ilike(like)) | (Customer.phone.ilike(like)) | (Customer.id_number.ilike(like))
        )
    return [customer_dict(c) for c in query.order_by(Customer.name).limit(100).all()]


@app.post("/api/customers")
def customers_create(payload: CustomerIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = Customer(**payload.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return customer_dict(c)


@app.get("/api/vehicles")
def vehicles_list(q: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(Vehicle).options(joinedload(Vehicle.customer))
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Vehicle.plate.ilike(like)) | (Vehicle.brand.ilike(like)) | (Vehicle.model.ilike(like))
        )
    return [vehicle_dict(v) for v in query.order_by(Vehicle.plate).limit(100).all()]


@app.post("/api/vehicles")
def vehicles_create(payload: VehicleIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not db.query(Customer).filter(Customer.id == payload.customer_id).first():
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    v = Vehicle(**payload.model_dump())
    db.add(v)
    db.commit()
    db.refresh(v)
    v = db.query(Vehicle).options(joinedload(Vehicle.customer)).filter(Vehicle.id == v.id).first()
    return vehicle_dict(v)


# ---------- Receptions ----------
@app.get("/api/receptions")
def receptions_list(
    status: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Reception).options(
        joinedload(Reception.vehicle).joinedload(Vehicle.customer),
        joinedload(Reception.damages),
        joinedload(Reception.photos),
        joinedload(Reception.diagnosis),
        joinedload(Reception.work_order).joinedload(WorkOrder.lines).joinedload(WorkOrderLine.part),
    )
    if status:
        query = query.filter(Reception.status == status)
    rows = query.order_by(Reception.created_at.desc()).limit(80).all()
    return [reception_dict(r) for r in rows]


def _load_reception(db: Session, reception_id: int) -> Reception:
    r = (
        db.query(Reception)
        .options(
            joinedload(Reception.vehicle).joinedload(Vehicle.customer),
            joinedload(Reception.damages),
            joinedload(Reception.photos),
            joinedload(Reception.diagnosis),
            joinedload(Reception.work_order).joinedload(WorkOrder.lines).joinedload(WorkOrderLine.part),
            joinedload(Reception.inspection_checks),
            joinedload(Reception.estimate).joinedload(Estimate.lines),
        )
        .filter(Reception.id == reception_id)
        .first()
    )
    if not r:
        raise HTTPException(status_code=404, detail="Recepción no encontrada")
    seed_inspection(db, r)
    ensure_public_token(r)
    db.commit()
    return r


@app.get("/api/receptions/{reception_id}")
def reception_get(reception_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = _load_reception(db, reception_id)
    return enrich_reception(r)


@app.post("/api/receptions")
def reception_create(payload: ReceptionIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    customer_id = payload.customer_id
    if payload.customer and not customer_id:
        cust = payload.customer.model_dump()
        if not str(cust.get("name") or "").strip():
            raise HTTPException(status_code=400, detail="Nombre de quien entrega es obligatorio")
        c = Customer(**cust)
        db.add(c)
        db.flush()
        customer_id = c.id
    if not customer_id:
        raise HTTPException(status_code=400, detail="Debe indicar o crear un cliente")

    vehicle_id = payload.vehicle_id
    if not vehicle_id:
        plate = (payload.plate or (payload.vehicle.plate if payload.vehicle else "")).upper().strip()
        brand = payload.brand or (payload.vehicle.brand if payload.vehicle else "")
        model = payload.model or (payload.vehicle.model if payload.vehicle else "")
        if not plate or not brand or not model:
            raise HTTPException(status_code=400, detail="Placa, marca y modelo son obligatorios")
        existing = db.query(Vehicle).filter(Vehicle.plate == plate).first()
        if existing:
            vehicle_id = existing.id
            existing.customer_id = customer_id
        else:
            v = Vehicle(
                customer_id=customer_id,
                plate=plate,
                brand=brand,
                model=model,
                year=payload.year or (payload.vehicle.year if payload.vehicle else 0),
                color=payload.color or (payload.vehicle.color if payload.vehicle else ""),
            )
            db.add(v)
            db.flush()
            vehicle_id = v.id

    reception = Reception(
        code=next_code(db, "REC", Reception),
        vehicle_id=vehicle_id,
        received_by=payload.received_by or user.name,
        odometer_km=payload.odometer_km,
        fuel_level=payload.fuel_level,
        customer_complaint=payload.customer_complaint,
        accessories=payload.accessories,
        status="recibido",
        promised_at=default_promise(payload.promised_hours or 24),
        customer_accepted=payload.customer_accepted,
        customer_signature_name=payload.customer_signature_name,
    )
    db.add(reception)
    db.flush()
    ensure_public_token(reception)
    seed_inspection(db, reception)
    for d in payload.damages:
        db.add(DamageItem(reception_id=reception.id, **d.model_dump()))
    db.commit()
    return reception_get(reception.id, db, user)


@app.patch("/api/receptions/{reception_id}/status")
def reception_status(
    reception_id: int,
    payload: StatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.services import STATUS_FLOW

    r = db.query(Reception).filter(Reception.id == reception_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Recepción no encontrada")
    status = (payload.status or "").strip()
    if status not in STATUS_FLOW:
        raise HTTPException(
            status_code=400,
            detail=f"Estado inválido. Use: {', '.join(STATUS_FLOW)}",
        )
    r.status = status
    r.updated_at = datetime.utcnow()
    if status == "entregado" and r.work_order:
        r.work_order.status = "cerrada"
        r.work_order.closed_at = datetime.utcnow()
    db.commit()
    return reception_get(reception_id, db, user)


@app.post("/api/receptions/{reception_id}/damages")
def reception_add_damage(
    reception_id: int,
    zone: str = Form(...),
    severity: str = Form("leve"),
    description: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    r = db.query(Reception).filter(Reception.id == reception_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Recepción no encontrada")
    item = DamageItem(
        reception_id=reception_id,
        zone=zone,
        severity=severity,
        description=description,
        present_on_arrival=True,
    )
    db.add(item)
    db.commit()
    return reception_get(reception_id, db, user)


@app.post("/api/receptions/{reception_id}/photos")
async def reception_photo(
    reception_id: int,
    file: UploadFile = File(...),
    caption: str = Form(""),
    zone: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    r = db.query(Reception).filter(Reception.id == reception_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Recepción no encontrada")
    raw_name = file.filename or "foto.jpg"
    ext = Path(raw_name).suffix.lower()
    if not ext and (file.content_type or "").startswith("image/"):
        mime = (file.content_type or "").split(";")[0].strip().lower()
        ext = {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/heic": ".heic",
            "image/heif": ".heif",
        }.get(mime, ".jpg")
    if not ext:
        ext = ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}:
        raise HTTPException(
            status_code=400,
            detail="Formato de imagen no permitido (use JPG, PNG, WEBP o HEIC)",
        )
    filename = f"rec{reception_id}_{uuid.uuid4().hex[:10]}{ext}"
    dest = UPLOADS_DIR / filename
    async with aiofiles.open(dest, "wb") as out:
        content = await file.read()
        await out.write(content)
    db.add(ReceptionPhoto(reception_id=reception_id, filename=filename, caption=caption, zone=zone))
    db.commit()
    return reception_get(reception_id, db, user)


# ---------- Diagnosis ----------
@app.post("/api/receptions/{reception_id}/diagnosis")
def diagnosis_upsert(
    reception_id: int,
    payload: DiagnosisIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    r = (
        db.query(Reception)
        .options(joinedload(Reception.diagnosis), joinedload(Reception.work_order))
        .filter(Reception.id == reception_id)
        .first()
    )
    if not r:
        raise HTTPException(status_code=404, detail="Recepción no encontrada")
    if r.diagnosis:
        for field, value in payload.model_dump(exclude={"create_work_order"}).items():
            setattr(r.diagnosis, field, value)
        r.diagnosis.updated_at = datetime.utcnow()
    else:
        r.diagnosis = Diagnosis(
            reception_id=reception_id,
            technician=payload.technician or user.name,
            symptoms=payload.symptoms,
            findings=payload.findings,
            obd_codes=payload.obd_codes,
            recommended_work=payload.recommended_work,
            estimated_hours=payload.estimated_hours,
            estimated_parts_cost=payload.estimated_parts_cost,
            estimated_labor_cost=payload.estimated_labor_cost,
            priority=payload.priority,
        )
        db.add(r.diagnosis)
    if r.status == "recibido":
        r.status = "en_diagnostico"
    if payload.create_work_order:
        wo = ensure_work_order(db, r, assigned_to=payload.technician or user.name)
        wo.assigned_to = payload.technician or user.name or wo.assigned_to
        if payload.estimated_hours:
            wo.labor_hours = payload.estimated_hours
        if payload.recommended_work:
            wo.labor_notes = payload.recommended_work
        if wo.status in ("abierta", "borrador", ""):
            wo.status = "en_proceso"
        recalculate_work_order(wo)
        if r.status in ("recibido", "en_diagnostico"):
            r.status = "en_reparacion"
    r.updated_at = datetime.utcnow()
    db.commit()
    return reception_get(reception_id, db, user)


# ---------- Work orders ----------
@app.get("/api/work-orders/{work_order_id}")
def work_order_get(work_order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    wo = (
        db.query(WorkOrder)
        .options(joinedload(WorkOrder.lines).joinedload(WorkOrderLine.part))
        .filter(WorkOrder.id == work_order_id)
        .first()
    )
    if not wo:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return work_order_dict(wo)


@app.patch("/api/work-orders/{work_order_id}")
def work_order_update(
    work_order_id: int,
    payload: WorkOrderUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    wo = db.query(WorkOrder).options(joinedload(WorkOrder.lines)).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(wo, field, value)
    recalculate_work_order(wo)
    reception = db.query(Reception).filter(Reception.id == wo.reception_id).first()
    if reception and payload.status:
        mapping = {
            "abierta": "en_reparacion",
            "en_proceso": "en_reparacion",
            "lista": "listo",
            "cerrada": "entregado",
        }
        if payload.status in mapping:
            reception.status = mapping[payload.status]
    db.commit()
    return work_order_get(work_order_id, db, user)


@app.post("/api/work-orders/{work_order_id}/lines")
def work_order_add_line(
    work_order_id: int,
    payload: WorkOrderLineIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    wo = (
        db.query(WorkOrder)
        .options(joinedload(WorkOrder.lines).joinedload(WorkOrderLine.part))
        .filter(WorkOrder.id == work_order_id)
        .first()
    )
    if not wo:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    if payload.part_id:
        part = db.query(Part).options(joinedload(Part.preferred_supplier)).filter(Part.id == payload.part_id).first()
        if not part:
            raise HTTPException(status_code=404, detail="Repuesto no encontrado")
        if part.stock_qty >= payload.quantity:
            try:
                reserve_part_for_work_order(db, wo, part, payload.quantity, user.name)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        else:
            try:
                po = create_purchase_for_part(
                    db,
                    part,
                    max(payload.quantity, part.min_stock or 1),
                    work_order_id=wo.id,
                    notes=f"Solicitado desde {wo.code}",
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            db.commit()
            return {
                "mode": "ordered",
                "message": f"Sin stock. Se creó pedido {po.code} a {part.preferred_supplier.name if part.preferred_supplier else 'proveedor'}.",
                "purchase_order_code": po.code,
                "work_order": work_order_dict(wo),
            }
        db.commit()
        return {"mode": "reserved", "message": "Repuesto reservado desde bodega.", "work_order": work_order_get(work_order_id, db, user)}

    price = payload.unit_price or 0
    line = WorkOrderLine(
        work_order_id=wo.id,
        description=payload.description,
        quantity=payload.quantity,
        unit_price=price,
        line_total=round(payload.quantity * price, 2),
        status="pendiente",
    )
    db.add(line)
    recalculate_work_order(wo)
    db.commit()
    return {"mode": "manual", "work_order": work_order_get(work_order_id, db, user)}


@app.post("/api/work-orders/{work_order_id}/request-part/{part_id}")
def work_order_request_part(
    work_order_id: int,
    part_id: int,
    quantity: float = 1,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    part = db.query(Part).options(joinedload(Part.preferred_supplier)).filter(Part.id == part_id).first()
    if not wo or not part:
        raise HTTPException(status_code=404, detail="Orden o repuesto no encontrado")
    try:
        po = create_purchase_for_part(db, part, quantity, work_order_id=wo.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return {"purchase_order_code": po.code, "message": "Pedido enviado a proveedor"}


# ---------- Inventory ----------
@app.get("/api/parts")
def parts_list(
    q: str = "",
    low_stock: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Part).options(joinedload(Part.preferred_supplier)).filter(Part.active.is_(True))
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Part.sku.ilike(like))
            | (Part.name.ilike(like))
            | (Part.brand.ilike(like))
            | (Part.compatible_with.ilike(like))
            | (Part.category.ilike(like))
        )
    parts = query.order_by(Part.name).limit(200).all()
    result = [part_dict(p) for p in parts]
    if low_stock:
        result = [p for p in result if p["low_stock"]]
    return result


@app.post("/api/parts")
def parts_create(payload: PartIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if db.query(Part).filter(Part.sku == payload.sku).first():
        raise HTTPException(status_code=400, detail="SKU ya existe")
    p = Part(**payload.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    p = db.query(Part).options(joinedload(Part.preferred_supplier)).filter(Part.id == p.id).first()
    return part_dict(p)


@app.put("/api/parts/{part_id}")
def parts_update(part_id: int, payload: PartIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = db.query(Part).filter(Part.id == part_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Repuesto no encontrado")
    for field, value in payload.model_dump().items():
        setattr(p, field, value)
    db.commit()
    p = db.query(Part).options(joinedload(Part.preferred_supplier)).filter(Part.id == part_id).first()
    return part_dict(p)


@app.post("/api/parts/{part_id}/adjust")
def parts_adjust(
    part_id: int,
    payload: StockAdjustIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.services import apply_stock_change

    p = db.query(Part).filter(Part.id == part_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Repuesto no encontrado")
    apply_stock_change(db, p, payload.quantity, payload.movement_type, note=payload.note, created_by=user.name)
    db.commit()
    p = db.query(Part).options(joinedload(Part.preferred_supplier)).filter(Part.id == part_id).first()
    return part_dict(p)


@app.get("/api/parts/lookup")
def parts_lookup(
    brand: str = "",
    model: str = "",
    q: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Busca repuestos compatibles mientras se diagnostica un carro."""
    query = db.query(Part).options(joinedload(Part.preferred_supplier)).filter(Part.active.is_(True))
    terms = [t for t in [brand, model, q] if t]
    parts = query.order_by(Part.name).limit(300).all()
    scored = []
    for p in parts:
        blob = f"{p.name} {p.brand} {p.compatible_with} {p.category}".lower()
        score = 0
        for t in terms:
            if t.lower() in blob:
                score += 1
        if not terms or score:
            item = part_dict(p)
            item["match_score"] = score
            scored.append(item)
    scored.sort(key=lambda x: (-x["match_score"], x["name"]))
    return scored[:50]


# ---------- Suppliers / Purchase orders ----------
from app.part_shops import build_search_link, build_whatsapp_order, shop_dict
from app.print_docs import diagnosis_print_html


def _ally_job_dict(job: AllyJob) -> dict:
    return {
        "id": job.id,
        "code": job.code,
        "ally_id": job.ally_id,
        "ally_name": job.ally.name if job.ally else "",
        "ally_phone": job.ally.phone if job.ally else "",
        "ally_whatsapp": (job.ally.whatsapp if job.ally else "") or "",
        "reception_id": job.reception_id,
        "work_order_id": job.work_order_id,
        "plate": job.plate,
        "vehicle_info": job.vehicle_info,
        "job_type": job.job_type,
        "description": job.description,
        "status": job.status,
        "cost_estimated": job.cost_estimated,
        "cost_final": job.cost_final,
        "sent_at": job.sent_at.isoformat() if job.sent_at else None,
        "due_at": job.due_at.isoformat() if job.due_at else None,
        "returned_at": job.returned_at.isoformat() if job.returned_at else None,
        "created_by": job.created_by,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "events": [
            {
                "id": e.id,
                "status": e.status,
                "note": e.note,
                "created_by": e.created_by,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in sorted(job.events or [], key=lambda x: x.created_at or datetime.min)
        ],
    }


@app.get("/api/suppliers")
def suppliers_list(
    kind: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Supplier).filter(Supplier.active.is_(True))
    if kind:
        query = query.filter(Supplier.kind == kind)
    rows = query.order_by(Supplier.kind, Supplier.name).all()
    return [shop_dict(s) for s in rows]


@app.post("/api/suppliers")
def suppliers_create(payload: SupplierIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = Supplier(**payload.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return shop_dict(s)


@app.get("/api/parts/market-search")
def parts_market_search(
    q: str = "",
    vehicle: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Buscar/comprar en tiendas proveedoras (Gigante, Guacamaya, etc.)."""
    shops = (
        db.query(Supplier)
        .filter(Supplier.active.is_(True), Supplier.kind == "tienda")
        .order_by(Supplier.name)
        .all()
    )
    query = (q or "").strip()
    results = []
    for s in shops:
        item = shop_dict(s)
        item["search_link"] = build_search_link(s, query)
        item["whatsapp_link"] = build_whatsapp_order(s, query or "repuesto", vehicle)
        results.append(item)
    return {"query": query, "vehicle": vehicle, "shops": results}


@app.get("/api/receptions/{reception_id}/diagnosis/print", response_class=HTMLResponse)
def diagnosis_print(
    reception_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    r = _load_reception(db, reception_id)
    settings = get_settings(db)
    return HTMLResponse(diagnosis_print_html(r, shop_name=settings.shop_name or "Aitorepuestos"))


@app.get("/api/ally-jobs")
def ally_jobs_list(
    status: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(AllyJob).options(
        joinedload(AllyJob.ally),
        joinedload(AllyJob.events),
    )
    if status:
        query = query.filter(AllyJob.status == status)
    rows = query.order_by(AllyJob.created_at.desc()).limit(120).all()
    return [_ally_job_dict(j) for j in rows]


@app.post("/api/ally-jobs")
def ally_jobs_create(
    payload: AllyJobIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ally = db.query(Supplier).filter(Supplier.id == payload.ally_id, Supplier.active.is_(True)).first()
    if not ally:
        raise HTTPException(status_code=404, detail="Aliado no encontrado")
    due = None
    if payload.due_at:
        try:
            due = datetime.fromisoformat(payload.due_at.replace("Z", ""))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Fecha due_at inválida") from exc
    job = AllyJob(
        code=next_code(db, "ALI", AllyJob),
        ally_id=payload.ally_id,
        reception_id=payload.reception_id,
        work_order_id=payload.work_order_id,
        plate=(payload.plate or "").upper().strip(),
        vehicle_info=payload.vehicle_info,
        job_type=payload.job_type or "otro",
        description=payload.description,
        status="cotizado",
        cost_estimated=payload.cost_estimated or 0,
        due_at=due,
        created_by=user.name,
    )
    db.add(job)
    db.flush()
    db.add(
        AllyJobEvent(
            job_id=job.id,
            status="cotizado",
            note="Trabajo registrado para aliado",
            created_by=user.name,
        )
    )
    db.commit()
    job = (
        db.query(AllyJob)
        .options(joinedload(AllyJob.ally), joinedload(AllyJob.events))
        .filter(AllyJob.id == job.id)
        .first()
    )
    return _ally_job_dict(job)


@app.patch("/api/ally-jobs/{job_id}")
def ally_jobs_update(
    job_id: int,
    payload: AllyJobUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = (
        db.query(AllyJob)
        .options(joinedload(AllyJob.ally), joinedload(AllyJob.events))
        .filter(AllyJob.id == job_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Seguimiento no encontrado")
    if payload.status:
        job.status = payload.status
        if payload.status == "enviado" and not job.sent_at:
            job.sent_at = datetime.utcnow()
        if payload.status == "recibido" and not job.returned_at:
            job.returned_at = datetime.utcnow()
    if payload.cost_final is not None:
        job.cost_final = payload.cost_final
    if payload.due_at:
        try:
            job.due_at = datetime.fromisoformat(payload.due_at.replace("Z", ""))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Fecha due_at inválida") from exc
    job.updated_at = datetime.utcnow()
    note = (payload.note or "").strip() or f"Estado → {job.status}"
    db.add(AllyJobEvent(job_id=job.id, status=job.status, note=note, created_by=user.name))
    db.commit()
    job = (
        db.query(AllyJob)
        .options(joinedload(AllyJob.ally), joinedload(AllyJob.events))
        .filter(AllyJob.id == job_id)
        .first()
    )
    return _ally_job_dict(job)


@app.get("/api/purchase-orders")
def purchase_orders_list(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(PurchaseOrder)
        .options(joinedload(PurchaseOrder.supplier), joinedload(PurchaseOrder.lines).joinedload(PurchaseOrderLine.part))
        .order_by(PurchaseOrder.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": po.id,
            "code": po.code,
            "status": po.status,
            "notes": po.notes,
            "total": po.total,
            "created_at": po.created_at.isoformat() if po.created_at else None,
            "received_at": po.received_at.isoformat() if po.received_at else None,
            "supplier": {"id": po.supplier.id, "name": po.supplier.name, "phone": po.supplier.phone},
            "work_order_id": po.work_order_id,
            "lines": [
                {
                    "id": line.id,
                    "part_id": line.part_id,
                    "part_name": line.part.name if line.part else "",
                    "sku": line.part.sku if line.part else "",
                    "quantity": line.quantity,
                    "unit_cost": line.unit_cost,
                    "line_total": line.line_total,
                }
                for line in po.lines
            ],
        }
        for po in rows
    ]


@app.post("/api/purchase-orders")
def purchase_orders_create(
    payload: PurchaseOrderIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not db.query(Supplier).filter(Supplier.id == payload.supplier_id).first():
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    po = PurchaseOrder(
        code=next_code(db, "OC", PurchaseOrder),
        supplier_id=payload.supplier_id,
        work_order_id=payload.work_order_id,
        notes=payload.notes,
        status="solicitado",
    )
    db.add(po)
    db.flush()
    total = 0.0
    from app.models import PurchaseOrderLine

    for raw in payload.lines:
        part = db.query(Part).filter(Part.id == raw.get("part_id")).first()
        if not part:
            continue
        qty = float(raw.get("quantity", 1))
        cost = float(raw.get("unit_cost", part.cost_price))
        line_total = round(qty * cost, 2)
        total += line_total
        db.add(
            PurchaseOrderLine(
                purchase_order_id=po.id,
                part_id=part.id,
                quantity=qty,
                unit_cost=cost,
                line_total=line_total,
            )
        )
    po.total = total
    db.commit()
    return {"id": po.id, "code": po.code}


@app.patch("/api/purchase-orders/{po_id}/status")
def purchase_order_status(
    po_id: int,
    payload: StatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    po = (
        db.query(PurchaseOrder)
        .options(joinedload(PurchaseOrder.lines).joinedload(PurchaseOrderLine.part), joinedload(PurchaseOrder.supplier))
        .filter(PurchaseOrder.id == po_id)
        .first()
    )
    if not po:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if payload.status == "recibido":
        receive_purchase_order(db, po, user.name)
    else:
        po.status = payload.status
    db.commit()
    return {"id": po.id, "code": po.code, "status": po.status}


# ---------- Pro: DVI / Estimate / Portal / Catalog / Appointments ----------
from pydantic import BaseModel


class InspectionUpdateIn(BaseModel):
    items: list[dict]


class EstimateActionIn(BaseModel):
    approved_line_ids: list[int] | None = None
    message: str = ""


class AppointmentIn(BaseModel):
    customer_name: str
    phone: str = ""
    plate: str = ""
    vehicle_info: str = ""
    reason: str = ""
    starts_at: str
    notes: str = ""


class ServiceAddIn(BaseModel):
    service_id: int
    work_order_id: int


@app.put("/api/receptions/{reception_id}/inspection")
def inspection_update(
    reception_id: int,
    payload: InspectionUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    r = _load_reception(db, reception_id)
    by_key = {c.system_key: c for c in r.inspection_checks}
    for item in payload.items:
        key = item.get("system_key")
        if key not in by_key:
            continue
        by_key[key].status = item.get("status", by_key[key].status)
        by_key[key].notes = item.get("notes", by_key[key].notes)
    if r.status == "recibido":
        r.status = "en_diagnostico"
    db.commit()
    return reception_get(reception_id, db, user)


@app.post("/api/receptions/{reception_id}/estimate")
def estimate_create(
    reception_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    r = _load_reception(db, reception_id)
    est = build_estimate_from_reception(db, r)
    db.commit()
    return {
        "estimate": estimate_dict_safe(est),
        "public_url": f"/t/{r.public_token}",
        "message": "Cotización lista. Envíe el link al cliente por WhatsApp.",
        "reception": enrich_reception(_load_reception(db, reception_id)),
    }


def estimate_dict_safe(est: Estimate):
    from app.pro import estimate_dict

    return estimate_dict(est)


class ServiceIn(BaseModel):
    name: str
    category: str = "General"
    hours: float = 1
    price: float = 0
    description: str = ""


class UserCreateIn(BaseModel):
    name: str
    username: str
    password: str
    role: str = "mecanico"


@app.get("/api/services")
def services_list(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(ServiceCatalog).filter(ServiceCatalog.active.is_(True)).order_by(ServiceCatalog.name).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "category": s.category,
            "hours": s.hours,
            "price": s.price,
            "description": s.description,
        }
        for s in rows
    ]


@app.post("/api/services")
def services_create(payload: ServiceIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = ServiceCatalog(**payload.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"id": s.id, "name": s.name, "category": s.category, "hours": s.hours, "price": s.price}


@app.get("/api/users")
def users_list(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo administrador")
    rows = db.query(User).order_by(User.name).all()
    return [{"id": u.id, "name": u.name, "username": u.username, "role": u.role, "active": u.active} for u in rows]


@app.post("/api/users")
def users_create(payload: UserCreateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.auth import hash_password

    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo administrador")
    if payload.role not in ("admin", "recepcion", "mecanico"):
        raise HTTPException(status_code=400, detail="Rol inválido")
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Usuario ya existe")
    u = User(
        name=payload.name,
        username=payload.username.strip().lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return {"id": u.id, "name": u.name, "username": u.username, "role": u.role}


@app.post("/api/work-orders/{work_order_id}/add-service")
def add_service_to_wo(
    work_order_id: int,
    payload: ServiceAddIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.models import WorkOrderLine

    wo = db.query(WorkOrder).options(joinedload(WorkOrder.lines)).filter(WorkOrder.id == work_order_id).first()
    svc = db.query(ServiceCatalog).filter(ServiceCatalog.id == payload.service_id).first()
    if not wo or not svc:
        raise HTTPException(status_code=404, detail="Orden o servicio no encontrado")
    wo.labor_hours = (wo.labor_hours or 0) + svc.hours
    wo.labor_notes = ((wo.labor_notes + "\n") if wo.labor_notes else "") + svc.name
    from app.services import recalculate_work_order

    recalculate_work_order(wo)
    db.commit()
    return work_order_dict(wo)


@app.get("/api/vehicles/{vehicle_id}/history")
def vehicle_history_api(vehicle_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return vehicle_history(db, vehicle_id)


@app.get("/api/appointments")
def appointments_list(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(Appointment).order_by(Appointment.starts_at.desc()).limit(50).all()
    return [
        {
            "id": a.id,
            "customer_name": a.customer_name,
            "phone": a.phone,
            "plate": a.plate,
            "vehicle_info": a.vehicle_info,
            "reason": a.reason,
            "starts_at": a.starts_at.isoformat(),
            "status": a.status,
            "notes": a.notes,
        }
        for a in rows
    ]


@app.post("/api/appointments")
def appointments_create(
    payload: AppointmentIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        starts = datetime.fromisoformat(payload.starts_at.replace("Z", ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Fecha inválida") from exc
    a = Appointment(
        customer_name=payload.customer_name,
        phone=payload.phone,
        plate=payload.plate.upper(),
        vehicle_info=payload.vehicle_info,
        reason=payload.reason,
        starts_at=starts,
        notes=payload.notes,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return {"id": a.id, "starts_at": a.starts_at.isoformat()}


@app.get("/api/public/{token}")
def public_get(token: str, db: Session = Depends(get_db)):
    data = public_payload(db, token)
    if not data:
        raise HTTPException(status_code=404, detail="Enlace no válido")
    return data


@app.post("/api/public/{token}/approve")
def public_approve(token: str, payload: EstimateActionIn, db: Session = Depends(get_db)):
    data = public_payload(db, token)
    if not data:
        raise HTTPException(status_code=404, detail="Enlace no válido")
    r = db.query(Reception).options(joinedload(Reception.estimate).joinedload(Estimate.lines)).filter(
        Reception.public_token == token
    ).first()
    if not r or not r.estimate:
        raise HTTPException(status_code=400, detail="No hay cotización")
    approve_estimate(db, r.estimate, payload.approved_line_ids)
    db.commit()
    return public_payload(db, token)


@app.post("/api/public/{token}/decline")
def public_decline(token: str, payload: EstimateActionIn, db: Session = Depends(get_db)):
    r = db.query(Reception).options(joinedload(Reception.estimate)).filter(Reception.public_token == token).first()
    if not r or not r.estimate:
        raise HTTPException(status_code=404, detail="No hay cotización")
    decline_estimate(db, r.estimate, payload.message)
    db.commit()
    return public_payload(db, token)


# ---------- Static / SPA ----------
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.get("/uploads/{filename}")
def uploaded_file(filename: str):
    safe = Path(filename).name
    path = UPLOADS_DIR / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(path)


@app.get("/api/health")
def health():
    from app.config import ENVIRONMENT, IS_PRODUCTION

    db_ok = False
    try:
        db = next(get_db())
        try:
            db.query(User).limit(1).all()
            db_ok = True
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        db_ok = False

    return {
        "ok": db_ok,
        "service": "katire",
        "environment": ENVIRONMENT,
        "production": IS_PRODUCTION,
        "fe": "hacienda-cr-v4.4",
        "db": db_ok,
        "build": "20260722f",
    }


@app.post("/api/bootstrap/workspace")
def bootstrap_workspace(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Asegura catálogo + cita + carro demo para que todos los menús tengan datos."""
    from app.seed import ensure_demo_catalog, ensure_demo_workspace
    from app.part_shops import ensure_default_shops

    ensure_default_shops(db)
    ensure_demo_catalog(db)
    ensure_demo_workspace(db)
    return {"ok": True, "message": "Patio, bodega, tiendas y citas listos"}


# ---------- Katire Facturación Electrónica CR ----------
from app.fe_cr import DOC_TYPES, IVA_RATES, ID_TYPES, CONDICION_VENTA, MEDIO_PAGO, HaciendaClient
from app.config import CERTS_DIR
from app.fe_service import (
    get_issuer,
    html_for_invoice,
    invoice_dict,
    issue_and_send,
    issue_from_work_order,
    issuer_dict,
    poll_hacienda_status,
    readiness,
    rebuild_xml,
    send_to_hacienda,
    sign_invoice,
)
from app.models import ElectronicInvoice, IssuerProfile


class IssuerIn(BaseModel):
    nombre: str = ""
    nombre_comercial: str = ""
    tipo_id: str = "02"
    numero_id: str = ""
    codigo_actividad: str = ""
    correo: str = ""
    telefono: str = ""
    provincia: str = "5"
    canton: str = "01"
    distrito: str = "01"
    otras_senas: str = ""
    sucursal: str = "001"
    terminal: str = "00001"
    ambiente: str = "sandbox"
    hacienda_user: str = ""
    hacienda_password: str = ""
    pin_cert: str = ""
    cabys_default_servicio: str = "8314100000000"
    cabys_default_repuesto: str = "4530000000000"


class IssueInvoiceIn(BaseModel):
    work_order_id: int
    tipo_documento: str = "01"
    condicion_venta: str = "01"
    medio_pago: str = "01"
    tarifa_codigo: str = "08"
    send_now: bool = False


@app.get("/api/fe/meta")
def fe_meta(user: User = Depends(get_current_user)):
    return {
        "doc_types": DOC_TYPES,
        "iva_rates": {k: {"label": v[0], "rate": float(v[1])} for k, v in IVA_RATES.items()},
        "id_types": ID_TYPES,
        "condicion_venta": CONDICION_VENTA,
        "medio_pago": MEDIO_PAGO,
        "brand": "Katire",
        "schema": "v4.4",
        "signing": "XAdES-EPES + .p12",
    }


@app.get("/api/fe/readiness")
def fe_readiness(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return readiness(db)


@app.get("/api/fe/issuer")
def fe_issuer_get(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return issuer_dict(get_issuer(db))


@app.put("/api/fe/issuer")
def fe_issuer_put(payload: IssuerIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role not in ("admin", "recepcion"):
        raise HTTPException(status_code=403, detail="Sin permiso para editar emisor FE")
    issuer = get_issuer(db)
    data = payload.model_dump()
    pwd = data.pop("hacienda_password", "")
    pin = data.pop("pin_cert", "")
    for k, v in data.items():
        setattr(issuer, k, v)
    if pwd:
        issuer.hacienda_password = pwd
    if pin:
        issuer.pin_cert = pin
    db.commit()
    return issuer_dict(issuer)


@app.post("/api/fe/cert")
async def fe_cert_upload(
    file: UploadFile = File(...),
    pin: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in ("admin", "recepcion"):
        raise HTTPException(status_code=403, detail="Sin permiso para subir certificado FE")
    name = Path(file.filename or "cert.p12").name
    ext = Path(name).suffix.lower()
    if ext not in {".p12", ".pfx"}:
        raise HTTPException(status_code=400, detail="Suba un certificado .p12 o .pfx")
    safe = f"emisor_{uuid.uuid4().hex[:10]}{ext}"
    dest = CERTS_DIR / safe
    content = await file.read()
    if len(content) < 100:
        raise HTTPException(status_code=400, detail="Archivo de certificado inválido")
    dest.write_bytes(content)
    issuer = get_issuer(db)
    # borra cert anterior si existe
    if issuer.cert_filename:
        old = CERTS_DIR / Path(issuer.cert_filename).name
        if old.exists() and old != dest:
            try:
                old.unlink()
            except OSError:
                pass
    issuer.cert_filename = safe
    if pin:
        issuer.pin_cert = pin
    db.commit()
    # Validar PIN si vino
    info = {"ok": True, "cert_filename": safe}
    if issuer.pin_cert:
        try:
            from app.fe_signer import try_validate_p12

            info.update(try_validate_p12(dest, issuer.pin_cert))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Certificado o PIN inválido: {exc}") from exc
    return {**info, "issuer": issuer_dict(issuer)}


@app.post("/api/fe/test-auth")
def fe_test_auth(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    issuer = get_issuer(db)
    if not issuer.hacienda_user or not issuer.hacienda_password:
        raise HTTPException(status_code=400, detail="Faltan credenciales ATV")
    try:
        client = HaciendaClient(issuer.ambiente)
        return client.authenticate(issuer.hacienda_user, issuer.hacienda_password)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/fe/invoices")
def fe_invoices(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(ElectronicInvoice)
        .options(joinedload(ElectronicInvoice.lines))
        .order_by(ElectronicInvoice.created_at.desc())
        .limit(100)
        .all()
    )
    return [invoice_dict(r) for r in rows]


@app.post("/api/fe/issue")
def fe_issue(payload: IssueInvoiceIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        if payload.send_now:
            return issue_and_send(
                db,
                payload.work_order_id,
                tipo_documento=payload.tipo_documento,
                condicion_venta=payload.condicion_venta,
                medio_pago=payload.medio_pago,
                tarifa_codigo=payload.tarifa_codigo,
            )
        inv = issue_from_work_order(
            db,
            payload.work_order_id,
            tipo_documento=payload.tipo_documento,
            condicion_venta=payload.condicion_venta,
            medio_pago=payload.medio_pago,
            tarifa_codigo=payload.tarifa_codigo,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return invoice_dict(inv)


@app.post("/api/fe/invoices/{invoice_id}/rebuild-xml")
def fe_rebuild(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        inv = rebuild_xml(db, invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return invoice_dict(inv)


@app.post("/api/fe/invoices/{invoice_id}/sign")
def fe_sign(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        inv = sign_invoice(db, invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "message": "XML firmado XAdES-EPES", "invoice": invoice_dict(inv)}


@app.post("/api/fe/invoices/{invoice_id}/send")
def fe_send(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return send_to_hacienda(db, invoice_id, wait_acceptance=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/fe/invoices/{invoice_id}/refresh-status")
def fe_refresh(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return poll_hacienda_status(db, invoice_id, attempts=6, wait_seconds=1.5)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/fe/invoices/{invoice_id}/xml")
def fe_xml(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    inv = db.query(ElectronicInvoice).filter(ElectronicInvoice.id == invoice_id).first()
    if not inv or not inv.xml_content:
        raise HTTPException(status_code=404, detail="XML no disponible")
    return Response(
        content=inv.xml_content,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{inv.clave}.xml"'},
    )


@app.get("/api/fe/invoices/{invoice_id}/print")
def fe_print(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        html = html_for_invoice(db, invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return HTMLResponse(html)


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/login")
def login_page():
    return FileResponse(WEB_DIR / "login.html")


@app.get("/t/{token}")
def track_page(token: str):
    return FileResponse(WEB_DIR / "track.html")
