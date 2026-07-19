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
from app.models import IssuerProfile, ShopSettings, User

# Identidad del negocio (Aitorepuestos) + producto (Katire)
SHOP = {
    "shop_name": "Aitorepuestos",
    "slogan": "De la llave al XML.",
    "phone": "+506 8870-8123",
    "whatsapp": "+506 8870-8123",
    "address": "Costa Rica",
    "labor_rate": 15000,  # tarifa hora sugerida; ajustable en Casa
    "currency": "CRC",
    "sinpe_phone": "88708123",
    "sinpe_name": "Aitorepuestos",
}

ISSUER = {
    "nombre": "Aitorepuestos",
    "nombre_comercial": "Aitorepuestos · Katire",
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
    user = db.query(User).filter(User.username == ADMIN_USERNAME).first()
    if user:
        user.active = True
        user.name = ADMIN_NAME or user.name
        user.role = "admin"
        user.password_hash = hash_password(ADMIN_PASSWORD)
    else:
        db.add(
            User(
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
    user = db.query(User).filter(User.username == DEMO_USERNAME).first()
    if user:
        user.active = True
        user.name = DEMO_NAME or user.name
        user.role = "recepcion"
        user.password_hash = hash_password(DEMO_PASSWORD)
    else:
        db.add(
            User(
                name=DEMO_NAME,
                username=DEMO_USERNAME,
                password_hash=hash_password(DEMO_PASSWORD),
                role="recepcion",
            )
        )
    db.commit()


def ensure_settings(db: Session) -> None:
    """Aplica identidad Aitorepuestos (datos del dueño)."""
    settings = db.query(ShopSettings).first()
    if not settings:
        settings = ShopSettings(**SHOP)
        db.add(settings)
    else:
        settings.shop_name = SHOP["shop_name"]
        settings.slogan = SHOP["slogan"]
        settings.phone = SHOP["phone"]
        settings.whatsapp = SHOP["whatsapp"]
        settings.address = SHOP["address"]
        if not settings.labor_rate:
            settings.labor_rate = SHOP["labor_rate"]
        if not getattr(settings, "sinpe_phone", None):
            settings.sinpe_phone = SHOP.get("sinpe_phone") or settings.whatsapp or settings.phone
        if not getattr(settings, "sinpe_name", None):
            settings.sinpe_name = SHOP.get("sinpe_name") or settings.shop_name
    db.commit()


def ensure_issuer(db: Session) -> None:
    """Emisor Hacienda: cédula y actividad de Aitorepuestos."""
    issuer = db.query(IssuerProfile).first()
    if not issuer:
        issuer = IssuerProfile(**ISSUER)
        db.add(issuer)
    else:
        for key, value in ISSUER.items():
            setattr(issuer, key, value)
    db.commit()


def seed_if_empty(db: Session) -> None:
    """Admin + demo cliente + identidad Aitorepuestos + emisor FE + tiendas. Sin demos de stock."""
    from app.part_shops import ensure_default_shops

    ensure_admin(db)
    ensure_demo_client(db)
    ensure_settings(db)
    ensure_issuer(db)
    ensure_default_shops(db)
