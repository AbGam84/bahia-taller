from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import ADMIN_NAME, ADMIN_PASSWORD, ADMIN_USERNAME
from app.models import ShopSettings, User


def ensure_admin(db: Session) -> None:
    user = db.query(User).filter(User.username == ADMIN_USERNAME).first()
    if user:
        # Solo asegura que exista y esté activo; no pisa la clave en cada arranque
        # salvo que nunca haya cambiado el hash inicial (instalación nueva).
        user.active = True
        if user.role != "admin":
            user.role = "admin"
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


def ensure_settings(db: Session) -> None:
    settings = db.query(ShopSettings).first()
    if settings:
        # Mantener identidad Katire si aún no personalizaron
        if not (settings.slogan or "").strip() or settings.slogan in (
            "El carro entra. La certeza sale.",
            "El patio cobra. Hacienda recibe.",
            "Diagnóstico claro. Repuesto listo. Servicio profesional.",
        ):
            settings.slogan = "De la llave al XML."
        if not (settings.shop_name or "").strip() or settings.shop_name in ("bahía", "TallerPro", "TallerPro Guanacaste"):
            settings.shop_name = "Katire"
        db.commit()
        return
    db.add(
        ShopSettings(
            shop_name="Katire",
            slogan="De la llave al XML.",
            phone="",
            whatsapp="",
            address="",
            labor_rate=0,
            currency="CRC",
        )
    )
    db.commit()


def seed_if_empty(db: Session) -> None:
    """Solo estructura vacía + admin inicial. Sin datos demo."""
    ensure_admin(db)
    ensure_settings(db)
