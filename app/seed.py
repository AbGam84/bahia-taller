from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import (
    ADMIN_NAME,
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    DEMO_NAME,
    DEMO_PASSWORD,
    DEMO_USERNAME,
)
from datetime import datetime, timedelta

from app.models import (
    Appointment,
    Customer,
    IssuerProfile,
    Part,
    Reception,
    ServiceCatalog,
    ShopSettings,
    User,
    Vehicle,
)
from app.pro import ensure_public_token, seed_inspection
from app.services import next_code

# Identidad del negocio (Autorespuesto) + producto (Katire)
SHOP = {
    "shop_name": "Autorespuesto",
    "slogan": "De la llave al XML.",
    "phone": "+506 8870-8123",
    "whatsapp": "+506 8870-8123",
    "address": "Costa Rica",
    "labor_rate": 15000,  # tarifa hora sugerida; ajustable en Casa
    "currency": "CRC",
    "sinpe_phone": "88708123",
    "sinpe_name": "Autorespuesto",
}

ISSUER = {
    "nombre": "Autorespuesto",
    "nombre_comercial": "Autorespuesto · Katire",
    "tipo_id": "01",  # Cédula Física
    "numero_id": "801390994",
    "codigo_actividad": "453001",  # Venta de partes/accesorios (confirmar en ATV si difiere)
    "correo": "",
    "telefono": "88708123",
    "provincia": "5",
    "canton": "01",
    "distrito": "01",
    "otras_senas": "Venta de repuestos y taller mecánico",
    "sucursal": "001",
    "terminal": "00001",
    "ambiente": "sandbox",
    "cabys_default_servicio": "8314100000000",
    "cabys_default_repuesto": "4530000000000",
}


def ensure_admin(db: Session) -> None:
    from app.tenancy import ensure_default_tenant

    tenant = ensure_default_tenant(db)
    user = db.query(User).filter(User.username == ADMIN_USERNAME).first()
    if user:
        user.active = True
        user.name = ADMIN_NAME or user.name
        user.role = "admin"
        user.password_hash = hash_password(ADMIN_PASSWORD)
        user.tenant_id = tenant.id
    else:
        db.add(
            User(
                tenant_id=tenant.id,
                name=ADMIN_NAME,
                username=ADMIN_USERNAME,
                password_hash=hash_password(ADMIN_PASSWORD),
                role="admin",
            )
        )
    db.commit()


def ensure_demo_client(db: Session) -> None:
    """Usuario para que el cliente mire el sistema y oriente el desarrollo."""
    if not DEMO_USERNAME or not DEMO_PASSWORD:
        return
    from app.tenancy import ensure_default_tenant

    tenant = ensure_default_tenant(db)
    user = db.query(User).filter(User.username == DEMO_USERNAME).first()
    if user:
        user.active = True
        user.name = DEMO_NAME or user.name
        user.role = "recepcion"
        user.password_hash = hash_password(DEMO_PASSWORD)
        user.tenant_id = tenant.id
    else:
        db.add(
            User(
                tenant_id=tenant.id,
                name=DEMO_NAME,
                username=DEMO_USERNAME,
                password_hash=hash_password(DEMO_PASSWORD),
                role="recepcion",
            )
        )
    db.commit()


def ensure_settings(db: Session) -> None:
    """Aplica identidad Autorespuesto (datos del dueño) solo al tenant default."""
    from app.tenancy import ensure_default_tenant, get_settings_for_tenant

    tenant = ensure_default_tenant(db)
    settings = get_settings_for_tenant(db, tenant.id)
    settings.shop_name = SHOP["shop_name"]
    settings.slogan = SHOP["slogan"]
    settings.phone = SHOP["phone"]
    settings.whatsapp = SHOP["whatsapp"]
    settings.address = SHOP["address"]
    if not settings.labor_rate:
        settings.labor_rate = SHOP["labor_rate"]
    settings.sinpe_phone = SHOP.get("sinpe_phone") or settings.whatsapp or settings.phone or settings.sinpe_phone
    settings.sinpe_name = SHOP.get("sinpe_name") or settings.shop_name
    db.commit()


def ensure_issuer(db: Session) -> None:
    """Emisor Hacienda: cédula y actividad de Autorespuesto."""
    from app.tenancy import ensure_default_tenant

    tenant = ensure_default_tenant(db)
    issuer = db.query(IssuerProfile).filter(IssuerProfile.tenant_id == tenant.id).first()
    if not issuer:
        issuer = db.query(IssuerProfile).first()
    if not issuer:
        issuer = IssuerProfile(tenant_id=tenant.id, **ISSUER)
        db.add(issuer)
    else:
        issuer.tenant_id = tenant.id
        for key, value in ISSUER.items():
            setattr(issuer, key, value)
    db.commit()


DEMO_PARTS = [
    {
        "sku": "PAD-FR-GEN",
        "barcode": "7501000000001",
        "name": "Pastillas de freno delanteras",
        "brand": "Generic",
        "category": "Frenos",
        "compatible_with": "Toyota Corolla, Yaris, Nissan Versa, Kia Rio",
        "location": "A1",
        "cost_price": 18000,
        "sale_price": 28000,
        "stock_qty": 8,
        "min_stock": 2,
    },
    {
        "sku": "FIL-ACE-01",
        "barcode": "7501000000002",
        "name": "Filtro de aceite",
        "brand": "Wix",
        "category": "Motor",
        "compatible_with": "Toyota, Nissan, Hyundai, Kia",
        "location": "B2",
        "cost_price": 3500,
        "sale_price": 6500,
        "stock_qty": 20,
        "min_stock": 5,
    },
    {
        "sku": "ACE-5W30",
        "barcode": "7501000000003",
        "name": "Aceite 5W-30 sintético 4L",
        "brand": "Mobil",
        "category": "Lubricantes",
        "compatible_with": "Gasolina general",
        "location": "B1",
        "cost_price": 16000,
        "sale_price": 24000,
        "stock_qty": 12,
        "min_stock": 3,
    },
    {
        "sku": "BAT-12V",
        "barcode": "7501000000004",
        "name": "Batería 12V 500CCA",
        "brand": "LTH",
        "category": "Eléctrico",
        "compatible_with": "Compactos / sedán",
        "location": "C1",
        "cost_price": 55000,
        "sale_price": 78000,
        "stock_qty": 3,
        "min_stock": 1,
    },
    {
        "sku": "AMP-TRAS",
        "barcode": "7501000000005",
        "name": "Amortiguador trasero",
        "brand": "KYB",
        "category": "Suspensión",
        "compatible_with": "Toyota Yaris, Corolla",
        "location": "D3",
        "cost_price": 32000,
        "sale_price": 48000,
        "stock_qty": 2,
        "min_stock": 1,
    },
]

DEMO_SERVICES = [
    {
        "name": "Diagnóstico computarizado",
        "category": "Diagnóstico",
        "hours": 1,
        "price": 15000,
        "description": "Lectura OBD + inspección básica",
    },
    {
        "name": "Cambio de aceite y filtro",
        "category": "Mantenimiento",
        "hours": 0.75,
        "price": 18000,
        "description": "Mano de obra (aceite/filtro aparte)",
    },
    {
        "name": "Cambio pastillas delanteras",
        "category": "Frenos",
        "hours": 1.5,
        "price": 25000,
        "description": "Incluye revisión de discos",
    },
    {
        "name": "Alineación / balanceo",
        "category": "Llantas",
        "hours": 1,
        "price": 20000,
        "description": "Servicio de patio / aliado",
    },
]


def ensure_demo_catalog(db: Session) -> None:
    """Catálogo base para que Bodega, Lectura y ficha tengan opciones usables."""
    from app.tenancy import ensure_default_tenant

    tenant = ensure_default_tenant(db)
    for row in DEMO_PARTS:
        existing = db.query(Part).filter(Part.sku == row["sku"], Part.tenant_id == tenant.id).first()
        if not existing:
            db.add(Part(tenant_id=tenant.id, **row))
        else:
            want = (row.get("barcode") or "").strip()
            have = (getattr(existing, "barcode", None) or "").strip()
            if want and (not have or have == existing.sku):
                existing.barcode = want
    for row in DEMO_SERVICES:
        if not db.query(ServiceCatalog).filter(
            ServiceCatalog.name == row["name"], ServiceCatalog.tenant_id == tenant.id
        ).first():
            db.add(ServiceCatalog(tenant_id=tenant.id, **row))
    for p in (
        db.query(Part)
        .filter(Part.tenant_id == tenant.id, (Part.barcode.is_(None)) | (Part.barcode == ""))
        .all()
    ):
        p.barcode = p.sku
    db.commit()


def ensure_demo_workspace(db: Session) -> None:
    """Datos vivos: siempre hay al menos un carro ABIERTO en el patio."""
    from app.tenancy import ensure_default_tenant

    tenant = ensure_default_tenant(db)
    open_statuses = ("recibido", "en_diagnostico", "esperando_repuestos", "en_reparacion", "listo")

    if not db.query(Appointment).filter(
        Appointment.status == "agendada", Appointment.tenant_id == tenant.id
    ).first():
        db.add(
            Appointment(
                tenant_id=tenant.id,
                customer_name="Cliente demo",
                phone="88880000",
                plate="CIT-01",
                vehicle_info="Toyota Yaris",
                reason="Frenos / revisión",
                starts_at=datetime.utcnow() + timedelta(hours=26),
                status="agendada",
                notes="Cita sembrada para mostrar el módulo",
            )
        )

    open_n = (
        db.query(Reception)
        .filter(Reception.tenant_id == tenant.id, Reception.status.in_(open_statuses))
        .count()
    )
    if open_n == 0:
        cust = (
            db.query(Customer)
            .filter(Customer.phone == "88881122", Customer.tenant_id == tenant.id)
            .first()
        )
        if not cust:
            cust = Customer(tenant_id=tenant.id, name="Demo Patio", phone="88881122", id_number="")
            db.add(cust)
            db.flush()
        veh = db.query(Vehicle).filter(Vehicle.plate == "DEMO-01").first()
        if not veh:
            veh = Vehicle(
                customer_id=cust.id,
                plate="DEMO-01",
                brand="Toyota",
                model="Yaris",
                year=2018,
                color="Blanco",
            )
            db.add(veh)
            db.flush()
        rec = (
            db.query(Reception)
            .filter(Reception.vehicle_id == veh.id, Reception.tenant_id == tenant.id)
            .order_by(Reception.id.desc())
            .first()
        )
        if rec and rec.status in ("entregado", "cancelado"):
            rec.status = "recibido"
            rec.customer_complaint = rec.customer_complaint or "Chillido al frenar — carro demo del patio"
            ensure_public_token(rec)
            seed_inspection(db, rec)
        elif not rec:
            rec = Reception(
                tenant_id=tenant.id,
                code=next_code(db, "REC", Reception),
                vehicle_id=veh.id,
                received_by="Katire",
                odometer_km=72000,
                fuel_level="1/2",
                customer_complaint="Chillido al frenar — carro demo del patio",
                accessories="",
                status="recibido",
                customer_accepted=True,
                customer_signature_name="Demo Patio",
            )
            db.add(rec)
            db.flush()
            ensure_public_token(rec)
            seed_inspection(db, rec)
        else:
            rec.status = "recibido"
            ensure_public_token(rec)
    db.commit()


def seed_if_empty(db: Session) -> None:
    """Admin + demo + identidad + FE + tiendas + catálogo + patio usable."""
    from app.part_shops import ensure_default_shops

    ensure_admin(db)
    ensure_demo_client(db)
    ensure_settings(db)
    ensure_issuer(db)
    ensure_default_shops(db)
    ensure_demo_catalog(db)
    ensure_demo_workspace(db)
