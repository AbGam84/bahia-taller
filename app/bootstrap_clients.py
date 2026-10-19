"""Clientes nombrados — licencia, taller, usuarios y logo."""

from __future__ import annotations

import shutil
import uuid
from datetime import date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import ROOT
from app.license import issue_license, license_fingerprint, parse_license
from app.models import IssuedLicense, IssuerProfile, ShopSettings, Tenant, User
from app.public_brand import find_issued_for_code, find_tenant_by_code, tenant_access_paths
from app.subscription import expiry_from_months
from app.tenancy import TENANT_UPLOADS

FYJ_AUTOMOTRIZ_NAME = "FyJ Automotriz"
FYJ_AUTOMOTRIZ_CODE = "fyj-automotriz"

FYJ_ADMIN_USERNAME = "frank"
FYJ_ADMIN_PASSWORD = "FyJDueno2026"
FYJ_ADMIN_NAME = "Frank — FyJ Automotriz"

FYJ_MECHANIC_USERNAME = "mecanico"
FYJ_MECHANIC_PASSWORD = "MecanicoKatire2026"
FYJ_MECHANIC_NAME = "Mecánico FyJ"

FYJ_LOGO_CANDIDATES = (
    ROOT / "clientes" / "fyj-automotriz" / "logo.jpeg",
    ROOT / "clientes" / "fyj-automotriz" / "logo.jpg",
    Path(r"C:\Users\PC\OneDrive\Escritorio\servicio de frank.jpeg"),
)

AUTO_REPUESTOS_KATIRE_NAME = "Auto Repuestos Katire"
AUTO_REPUESTOS_KATIRE_CODE = "auto-repuestos-katire"

KATIRE_ADMIN_USERNAME = "norma"
KATIRE_ADMIN_PASSWORD = "Katire.Oct2026"
KATIRE_ADMIN_NAME = "Norma Yelitza Rojas Santiago"

KATIRE_VENTAS_USERNAME = "ventas"
KATIRE_VENTAS_PASSWORD = "VentasKatire2026"
KATIRE_VENTAS_NAME = "Mostrador — Katire"

KATIRE_ADDRESS = (
    "Guanacaste, Santa Cruz, Tamarindo — del Colegio Educarte 300 m norte, camino a Huacas"
)

KATIRE_ISSUER = {
    "nombre": "Norma Yelitza Rojas Santiago",
    "nombre_comercial": AUTO_REPUESTOS_KATIRE_NAME,
    "tipo_id": "01",
    "numero_id": "801390994",
    "codigo_actividad": "453001",
    "correo": "",
    "telefono": "63706546",
    "provincia": "5",
    "canton": "03",
    "distrito": "01",
    "otras_senas": KATIRE_ADDRESS,
    "sucursal": "001",
    "terminal": "00001",
    "ambiente": "sandbox",
    "cabys_default_servicio": "8314100000000",
    "cabys_default_repuesto": "4530000000000",
}


def _logo_source() -> Path | None:
    for p in FYJ_LOGO_CANDIDATES:
        if p.is_file():
            return p
    return None


def install_tenant_logo_file(db: Session, tenant: Tenant, src: Path) -> None:
    ext = src.suffix.lower() or ".jpeg"
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        ext = ".jpeg"
    folder = TENANT_UPLOADS / str(tenant.id)
    folder.mkdir(parents=True, exist_ok=True)
    if tenant.logo_filename:
        old = folder / tenant.logo_filename
        if old.exists():
            old.unlink()
    fname = f"logo-{uuid.uuid4().hex[:10]}{ext}"
    shutil.copy2(src, folder / fname)
    tenant.logo_filename = fname
    db.add(tenant)


def ensure_fyj_automotriz_license(db: Session) -> dict | None:
    """Emite licencia mensual FyJ si aún no hay registro (idempotente)."""
    if find_issued_for_code(db, FYJ_AUTOMOTRIZ_CODE):
        return None
    exp = expiry_from_months(1)
    note = "Plan mensual · FyJ Automotriz"
    key = issue_license(FYJ_AUTOMOTRIZ_NAME, exp, seats=2, note=note)
    parse_license(key)
    row = IssuedLicense(
        shop_name=FYJ_AUTOMOTRIZ_NAME,
        license_key=key,
        seats=2,
        expires=exp,
        note=note,
        monthly_fee_crc=58000,
        paid_months_total=1,
        last_paid_at=datetime.utcnow(),
        active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    paths = tenant_access_paths(FYJ_AUTOMOTRIZ_CODE)
    return {
        "shop_name": row.shop_name,
        "expires": row.expires,
        "license_id": row.id,
        **paths,
        "activation_url": f"{paths['activar_url']}?key={key}",
    }


def _upsert_user(
    db: Session,
    *,
    tenant_id: int,
    username: str,
    name: str,
    role: str,
    password: str,
) -> User:
    uname = username.strip().lower()
    u = db.query(User).filter(User.username == uname).first()
    if u:
        u.tenant_id = tenant_id
        u.name = name
        u.role = role
        u.password_hash = hash_password(password)
        u.active = True
    else:
        u = User(
            tenant_id=tenant_id,
            username=uname,
            name=name,
            role=role,
            password_hash=hash_password(password),
            active=True,
        )
        db.add(u)
    return u


def ensure_fyj_automotriz_ready(db: Session) -> dict:
    """Licencia + taller activo + dueño + mecánico + logo (idempotente)."""
    ensure_fyj_automotriz_license(db)
    issued = find_issued_for_code(db, FYJ_AUTOMOTRIZ_CODE)
    if not issued:
        return {"ok": False, "message": "No se pudo emitir licencia FyJ"}

    key = (issued.license_key or "").strip()
    fp = license_fingerprint(key)
    data = parse_license(key)

    tenant = find_tenant_by_code(db, FYJ_AUTOMOTRIZ_CODE)
    if not tenant:
        tenant = db.query(Tenant).filter(Tenant.license_fp == fp).first()
    if not tenant:
        tenant = Tenant(
            code=FYJ_AUTOMOTRIZ_CODE,
            name=FYJ_AUTOMOTRIZ_NAME,
            license_key=key,
            license_fp=fp,
            seats=int(data.get("seats") or 2),
            expires=str(data.get("exp") or issued.expires or ""),
            monthly_fee_crc=int(issued.monthly_fee_crc or 58000),
            active=True,
        )
        db.add(tenant)
        db.flush()
        db.add(
            ShopSettings(
                tenant_id=tenant.id,
                shop_name=FYJ_AUTOMOTRIZ_NAME,
                slogan="Servicio automotriz de calidad.",
                sinpe_name=FYJ_AUTOMOTRIZ_NAME,
            )
        )
    else:
        tenant.code = FYJ_AUTOMOTRIZ_CODE
        tenant.name = FYJ_AUTOMOTRIZ_NAME
        tenant.license_key = key
        tenant.license_fp = fp
        tenant.expires = str(data.get("exp") or issued.expires or tenant.expires or "")
        tenant.active = True
        tenant.seats = int(data.get("seats") or tenant.seats or 2)

    mech_user = FYJ_MECHANIC_USERNAME
    taken = db.query(User).filter(User.username == mech_user).first()
    if taken and taken.tenant_id != tenant.id:
        mech_user = "fyj-mecanico"

    admin = _upsert_user(
        db,
        tenant_id=tenant.id,
        username=FYJ_ADMIN_USERNAME,
        name=FYJ_ADMIN_NAME,
        role="admin",
        password=FYJ_ADMIN_PASSWORD,
    )
    mech = _upsert_user(
        db,
        tenant_id=tenant.id,
        username=mech_user,
        name=FYJ_MECHANIC_NAME,
        role="mecanico",
        password=FYJ_MECHANIC_PASSWORD,
    )

    logo_src = _logo_source()
    if logo_src:
        install_tenant_logo_file(db, tenant, logo_src)

    from app.part_shops import ensure_default_shops

    ensure_default_shops(db, tenant.id)

    db.commit()
    db.refresh(tenant)
    paths = tenant_access_paths(FYJ_AUTOMOTRIZ_CODE)
    return {
        "ok": True,
        "tenant_code": tenant.code,
        "shop_name": tenant.name,
        "paid_until": tenant.expires,
        **paths,
        "admin_username": admin.username,
        "mechanic_username": mech.username,
        "logo_installed": bool(logo_src and tenant.logo_filename),
    }


def ensure_fyj_automotriz_license_only(db: Session) -> dict | None:
    """Compat: solo licencia (usado en imports antiguos)."""
    return ensure_fyj_automotriz_license(db)


def _monthly_license_row(db: Session, *, code: str, shop_name: str, note: str) -> IssuedLicense:
    """Emite licencia 1 mes si no existe; si venció, renueva (no rota clave mientras siga vigente)."""
    issued = find_issued_for_code(db, code)
    if issued:
        exp_s = (issued.expires or "")[:10]
        try:
            still_ok = datetime.strptime(exp_s, "%Y-%m-%d").date() >= date.today()
        except ValueError:
            still_ok = False
        if still_ok:
            return issued
        seats = int(issued.seats or 2)
    else:
        seats = 2
    exp = expiry_from_months(1)
    key = issue_license(shop_name, exp, seats=seats, note=note)
    parse_license(key)
    if issued:
        issued.license_key = key
        issued.expires = exp
        issued.active = True
        issued.last_paid_at = datetime.utcnow()
        issued.paid_months_total = int(issued.paid_months_total or 0) + 1
        db.add(issued)
        db.commit()
        db.refresh(issued)
        return issued
    row = IssuedLicense(
        shop_name=shop_name,
        license_key=key,
        seats=seats,
        expires=exp,
        note=note,
        monthly_fee_crc=58000,
        paid_months_total=1,
        last_paid_at=datetime.utcnow(),
        active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def ensure_auto_repuestos_katire_ready(db: Session) -> dict:
    """Licencia mensual + taller aislado + dueña + mostrador (Norma · Tamarindo)."""
    note = f"Plan mensual · {AUTO_REPUESTOS_KATIRE_NAME}"
    issued = _monthly_license_row(
        db,
        code=AUTO_REPUESTOS_KATIRE_CODE,
        shop_name=AUTO_REPUESTOS_KATIRE_NAME,
        note=note,
    )
    key = (issued.license_key or "").strip()
    fp = license_fingerprint(key)
    data = parse_license(key)

    tenant = find_tenant_by_code(db, AUTO_REPUESTOS_KATIRE_CODE)
    if not tenant:
        tenant = db.query(Tenant).filter(Tenant.license_fp == fp).first()
    if not tenant:
        tenant = Tenant(
            code=AUTO_REPUESTOS_KATIRE_CODE,
            name=AUTO_REPUESTOS_KATIRE_NAME,
            license_key=key,
            license_fp=fp,
            seats=int(data.get("seats") or 2),
            expires=str(data.get("exp") or issued.expires or ""),
            monthly_fee_crc=int(issued.monthly_fee_crc or 58000),
            active=True,
        )
        db.add(tenant)
        db.flush()
        db.add(
            ShopSettings(
                tenant_id=tenant.id,
                shop_name=AUTO_REPUESTOS_KATIRE_NAME,
                slogan="Repuestos y accesorios · Tamarindo",
                phone="+506 6370-6546",
                whatsapp="+506 6370-6546",
                address=KATIRE_ADDRESS,
                sinpe_phone="63706546",
                sinpe_name=AUTO_REPUESTOS_KATIRE_NAME,
            )
        )
    else:
        tenant.code = AUTO_REPUESTOS_KATIRE_CODE
        tenant.name = AUTO_REPUESTOS_KATIRE_NAME
        tenant.license_key = key
        tenant.license_fp = fp
        tenant.expires = str(data.get("exp") or issued.expires or tenant.expires or "")
        tenant.active = True
        tenant.seats = int(data.get("seats") or tenant.seats or 2)
        settings = db.query(ShopSettings).filter(ShopSettings.tenant_id == tenant.id).first()
        if settings:
            settings.shop_name = AUTO_REPUESTOS_KATIRE_NAME
            settings.address = KATIRE_ADDRESS
            settings.sinpe_name = AUTO_REPUESTOS_KATIRE_NAME

    issuer = db.query(IssuerProfile).filter(IssuerProfile.tenant_id == tenant.id).first()
    if not issuer:
        issuer = IssuerProfile(tenant_id=tenant.id, **KATIRE_ISSUER)
        db.add(issuer)
    else:
        for k, v in KATIRE_ISSUER.items():
            setattr(issuer, k, v)

    ventas_user = KATIRE_VENTAS_USERNAME
    taken = db.query(User).filter(User.username == ventas_user).first()
    if taken and taken.tenant_id != tenant.id:
        ventas_user = "katire-ventas"

    admin = _upsert_user(
        db,
        tenant_id=tenant.id,
        username=KATIRE_ADMIN_USERNAME,
        name=KATIRE_ADMIN_NAME,
        role="admin",
        password=KATIRE_ADMIN_PASSWORD,
    )
    ventas = _upsert_user(
        db,
        tenant_id=tenant.id,
        username=ventas_user,
        name=KATIRE_VENTAS_NAME,
        role="recepcion",
        password=KATIRE_VENTAS_PASSWORD,
    )

    from app.part_shops import ensure_default_shops

    ensure_default_shops(db, tenant.id)

    db.commit()
    db.refresh(tenant)
    paths = tenant_access_paths(AUTO_REPUESTOS_KATIRE_CODE)
    return {
        "ok": True,
        "tenant_code": tenant.code,
        "shop_name": tenant.name,
        "paid_until": tenant.expires,
        **paths,
        "admin_username": admin.username,
        "ventas_username": ventas.username,
    }
