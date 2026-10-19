"""Producción: sin login público demo en tenant Autorespuesto legado."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import ADMIN_USERNAME, DEMO_USERNAME, IS_PRODUCTION, LOCK_LEGACY_PUBLIC_LOGIN
from app.models import LicenseDevice, Tenant, User

_TEST_DEVICE_PREFIXES = ("dev-", "test-", "chk-")


def prune_automated_test_devices(db: Session) -> None:
    """Libera cupos consumidos por pruebas automáticas (no bloquea al cliente real)."""
    if not IS_PRODUCTION:
        return
    changed = False
    for row in db.query(LicenseDevice).filter(LicenseDevice.active.is_(True)):
        did = (row.device_id or "").strip().lower()
        if did == "test-dev" or any(did.startswith(p) for p in _TEST_DEVICE_PREFIXES):
            row.active = False
            changed = True
    if changed:
        db.commit()


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
