"""Multi-taller: cada cliente Katire es un Tenant independiente."""

from __future__ import annotations

import re
import shutil
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import get_current_user, hash_password
from app.config import DATA_DIR, IS_PRODUCTION
from app.license import license_fingerprint, license_status, load_stored_key, parse_license
from app.models import ShopSettings, Tenant, User

TENANT_UPLOADS = DATA_DIR / "tenants"
TENANT_UPLOADS.mkdir(parents=True, exist_ok=True)


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return (text or "taller")[:36]


def tenant_id_of(user: User) -> int:
    tid = getattr(user, "tenant_id", None) or 0
    if not tid:
        raise HTTPException(status_code=400, detail="Usuario sin taller asignado")
    return int(tid)


def ensure_default_tenant(db: Session) -> Tenant:
    """Crea el tenant Autorespuesto y backfill tenant_id en tablas existentes."""
    t = db.query(Tenant).filter(Tenant.code == "autorespuesto").first()
    if not t:
        t = db.query(Tenant).order_by(Tenant.id.asc()).first()
    if not t:
        t = Tenant(
            code="autorespuesto",
            name="Autorespuesto",
            seats=2,
            expires="2027-07-21",
            active=True,
        )
        db.add(t)
        db.flush()
    # Adjuntar licencia de instancia si el tenant aún no tiene
    if not (t.license_key or "").strip():
        key = load_stored_key()
        if key:
            try:
                data = parse_license(key)
                t.license_key = key
                t.license_fp = license_fingerprint(key)
                t.seats = int(data.get("seats") or t.seats or 2)
                t.expires = str(data.get("exp") or t.expires or "")
                if data.get("shop"):
                    t.name = str(data["shop"])
            except ValueError:
                pass
    for model in (User, ShopSettings):
        db.query(model).filter((model.tenant_id.is_(None)) | (model.tenant_id == 0)).update(
            {model.tenant_id: t.id}, synchronize_session=False
        )
    from app.models import Appointment, Customer, IssuerProfile, Part, Reception, ServiceCatalog, Supplier

    for model in (Customer, Part, Reception, Supplier, Appointment, ServiceCatalog, IssuerProfile):
        try:
            db.query(model).filter((model.tenant_id.is_(None)) | (model.tenant_id == 0)).update(
                {model.tenant_id: t.id}, synchronize_session=False
            )
        except Exception:
            pass
    db.commit()
    db.refresh(t)
    return t


def get_settings_for_tenant(db: Session, tenant_id: int) -> ShopSettings:
    settings = db.query(ShopSettings).filter(ShopSettings.tenant_id == tenant_id).first()
    if not settings:
        settings = ShopSettings(tenant_id=tenant_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def tenant_logo_path(tenant: Tenant) -> Path | None:
    if not tenant.logo_filename:
        return None
    p = TENANT_UPLOADS / str(tenant.id) / tenant.logo_filename
    return p if p.exists() else None


def tenant_license_status(tenant: Tenant | None) -> dict:
    """Estado de licencia del taller (no de la instancia global)."""
    if not tenant:
        return {
            "ok": False,
            "mode": "missing",
            "message": "Taller no encontrado",
            "shop": None,
            "expires": None,
            "seats": 0,
        }
    if not tenant.active:
        return {
            "ok": False,
            "mode": "disabled",
            "message": "Este taller está desactivado. Contacte a Katire.",
            "shop": tenant.name,
            "expires": tenant.expires,
            "seats": tenant.seats,
        }
    key = (tenant.license_key or "").strip()
    if key:
        try:
            data = parse_license(key)
            return {
                "ok": True,
                "mode": "licensed",
                "message": "Licencia Katire activa",
                "shop": data.get("shop") or tenant.name,
                "expires": data.get("exp") or tenant.expires,
                "seats": int(data.get("seats") or tenant.seats or 2),
                "note": data.get("note") or "",
                "tenant_code": tenant.code,
            }
        except ValueError as exc:
            return {
                "ok": False,
                "mode": "invalid",
                "message": str(exc),
                "shop": tenant.name,
                "expires": tenant.expires,
                "seats": 0,
                "tenant_code": tenant.code,
            }
    # Sin clave en tenant: legado / desarrollo
    if not IS_PRODUCTION:
        return {
            "ok": True,
            "mode": "development",
            "message": "Desarrollo local",
            "shop": tenant.name,
            "expires": None,
            "seats": 99,
            "tenant_code": tenant.code,
        }
    st = license_status()
    st = {**st, "tenant_code": tenant.code, "shop": st.get("shop") or tenant.name}
    return st


def activate_tenant(
    db: Session,
    *,
    license_key: str,
    admin_name: str,
    admin_username: str,
    admin_password: str,
    shop_name: str = "",
) -> dict:
    """Activa licencia → crea taller + admin. No afecta otros tenants."""
    data = parse_license(license_key)
    fp = license_fingerprint(license_key)
    existing = db.query(Tenant).filter(Tenant.license_fp == fp).first()
    if existing and existing.active:
        has_user = db.query(User).filter(User.tenant_id == existing.id).first()
        if has_user:
            raise ValueError(
                f"Esta licencia ya está activa para «{existing.name}» (código {existing.code}). "
                "Entre con el código del taller, usuario y clave."
            )
        tenant = existing
    else:
        name = (shop_name or data.get("shop") or "Taller").strip()
        code = slugify(name)
        base = code
        n = 2
        while db.query(Tenant).filter(Tenant.code == code).first():
            code = f"{base}-{n}"
            n += 1
        tenant = Tenant(
            code=code,
            name=name,
            license_key=license_key.strip(),
            license_fp=fp,
            seats=int(data.get("seats") or 2),
            expires=str(data.get("exp") or ""),
            active=True,
        )
        db.add(tenant)
        db.flush()
        s = ShopSettings(
            tenant_id=tenant.id,
            shop_name=name,
            slogan="De la llave al XML.",
            sinpe_name=name,
        )
        db.add(s)

    uname = admin_username.strip().lower()
    if db.query(User).filter(User.username == uname).first():
        raise ValueError("Ese usuario ya existe. Elija otro nombre de usuario.")
    if len(admin_password or "") < 6:
        raise ValueError("La clave debe tener al menos 6 caracteres")
    user = User(
        tenant_id=tenant.id,
        name=(admin_name or "Administrador").strip(),
        username=uname,
        password_hash=hash_password(admin_password),
        role="admin",
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(tenant)
    db.refresh(user)
    return {
        "tenant": tenant_dict(tenant),
        "user": {"id": user.id, "username": user.username, "name": user.name, "role": user.role},
        "login_hint": {
            "tenant_code": tenant.code,
            "username": user.username,
            "url": "/login",
        },
        "message": "Taller activado. Guarde su código, usuario y clave.",
    }


def save_tenant_logo(db: Session, tenant: Tenant, upload: UploadFile) -> Tenant:
    """Guarda logo solo de este taller (no toca otros)."""
    ext = Path(upload.filename or "logo.png").suffix.lower() or ".png"
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        raise ValueError("Use PNG, JPG o WEBP")
    folder = TENANT_UPLOADS / str(tenant.id)
    folder.mkdir(parents=True, exist_ok=True)
    # limpia logo anterior
    if tenant.logo_filename:
        old = folder / tenant.logo_filename
        if old.exists():
            old.unlink()
    fname = f"logo-{uuid.uuid4().hex[:10]}{ext}"
    dest = folder / fname
    with dest.open("wb") as out:
        shutil.copyfileobj(upload.file, out)
    tenant.logo_filename = fname
    db.commit()
    db.refresh(tenant)
    return tenant


def tenant_dict(t: Tenant) -> dict:
    return {
        "id": t.id,
        "code": t.code,
        "name": t.name,
        "seats": t.seats,
        "expires": t.expires,
        "logo_url": f"/api/branding/{t.code}/logo" if t.logo_filename else "/static/brand/logo.png",
        "active": t.active,
        "created_at": t.created_at.isoformat() if isinstance(t.created_at, datetime) else None,
    }


def require_tenant_user(user: User = Depends(get_current_user)) -> User:
    if not getattr(user, "tenant_id", None):
        raise HTTPException(status_code=400, detail="Usuario sin taller asignado")
    return user
