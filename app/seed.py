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
    if db.query(ShopSettings).first():
        return
    db.add(
        ShopSettings(
            shop_name="",
            slogan="",
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
