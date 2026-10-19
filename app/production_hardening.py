"""Producción: sin login público demo en tenant Autorespuesto legado."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import ADMIN_USERNAME, DEMO_USERNAME, IS_PRODUCTION, LOCK_LEGACY_PUBLIC_LOGIN
from app.models import Tenant, User


def disable_legacy_public_logins(db: Session) -> None:
    if not IS_PRODUCTION or not LOCK_LEGACY_PUBLIC_LOGIN:
        return
    tenant = db.query(Tenant).filter(Tenant.code == "autorespuesto").first()
    if not tenant:
        return
    names = {n.strip().lower() for n in (ADMIN_USERNAME, DEMO_USERNAME, "admin", "cliente") if n}
    for uname in names:
        row = (
            db.query(User)
            .filter(User.username == uname, User.tenant_id == tenant.id)
            .first()
        )
        if row:
            row.active = False
    db.commit()
