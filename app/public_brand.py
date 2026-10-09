"""URLs y perfil público por taller (código en la ruta /acceso/{code})."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import IssuedLicense, Tenant, User
from app.tenancy import slugify, tenant_dict


def resolve_tenant_code(code: str) -> str:
    return slugify((code or "").strip()) or "taller"


def find_tenant_by_code(db: Session, code: str) -> Tenant | None:
    c = resolve_tenant_code(code)
    return db.query(Tenant).filter(Tenant.code == c).first()


def find_issued_for_code(db: Session, code: str) -> IssuedLicense | None:
    c = resolve_tenant_code(code)
    for row in db.query(IssuedLicense).filter(IssuedLicense.active.is_(True)).order_by(IssuedLicense.id.desc()):
        if slugify(row.shop_name) == c:
            return row
    return None


def tenant_access_paths(code: str, *, base: str = "") -> dict:
    c = resolve_tenant_code(code)
    prefix = (base or "").rstrip("/")
    login = f"/acceso/{c}"
    activar = f"{login}/activar"
    if prefix:
        login = f"{prefix}{login}"
        activar = f"{prefix}{activar}"
    return {"code": c, "login_url": login, "activar_url": activar, "access_url": login}


def public_tenant_profile(db: Session, code: str, *, public_base: str = "") -> dict:
    c = resolve_tenant_code(code)
    paths = tenant_access_paths(c, base=public_base)
    tenant = find_tenant_by_code(db, c)
    if tenant:
        has_users = db.query(User.id).filter(User.tenant_id == tenant.id).limit(1).first() is not None
        td = tenant_dict(tenant)
        return {
            "ok": True,
            "code": c,
            "name": tenant.name,
            "shop_name": tenant.name,
            "logo_url": td["logo_url"],
            "activated": has_users,
            "pending_activation": not has_users,
            **paths,
        }
    issued = find_issued_for_code(db, c)
    if issued:
        return {
            "ok": True,
            "code": c,
            "name": issued.shop_name,
            "shop_name": issued.shop_name,
            "logo_url": "/static/brand/logo.png",
            "activated": False,
            "pending_activation": True,
            "expires": issued.expires,
            "license_issued": True,
            **paths,
        }
    return {
        "ok": False,
        "code": c,
        "name": "",
        "shop_name": "",
        "logo_url": "/static/brand/logo.png",
        "activated": False,
        "pending_activation": True,
        "message": "Taller no encontrado. Verifique el enlace o contacte a Katire.",
        **paths,
    }
