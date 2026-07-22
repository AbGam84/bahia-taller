"""Rutas del panel vendor Katire (dueño del software, no del taller)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import ALGORITHM, create_access_token, hash_password, security
from app.config import (
    COPYRIGHT,
    DEFAULT_LICENSE_SEATS,
    PRODUCT_NAME,
    SECRET_KEY,
    VENDOR_NAME,
    VENDOR_PASSWORD,
    VENDOR_USERNAME,
)
from app.database import get_db
from app.license import (
    current_seats,
    issue_license,
    license_fingerprint,
    license_status,
    load_stored_key,
    parse_license,
    save_license,
)
from app.models import IssuedLicense, LicenseDevice, User

router = APIRouter(prefix="/api/vendor", tags=["vendor"])


class VendorLoginIn(BaseModel):
    username: str
    password: str


class LicenseCreateIn(BaseModel):
    shop_name: str
    expires: str  # YYYY-MM-DD
    seats: int = Field(default=2, ge=1, le=50)
    note: str = ""
    contact_name: str = ""
    contact_phone: str = ""
    activate_here: bool = False  # activar en esta instancia


class ShopUserIn(BaseModel):
    name: str
    username: str
    password: str
    role: str = "recepcion"  # admin | recepcion | mecanico


def get_vendor(creds=Depends(security)):
    if creds is None:
        raise HTTPException(status_code=401, detail="Vendor: inicie sesión")
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Token vendor inválido") from exc
    if payload.get("role") != "vendor" or payload.get("sub") != VENDOR_USERNAME:
        raise HTTPException(status_code=403, detail="Solo el administrador Katire (vendor)")
    return {"username": VENDOR_USERNAME, "name": VENDOR_NAME, "role": "vendor"}


@router.post("/login")
def vendor_login(payload: VendorLoginIn):
    if payload.username.strip() != VENDOR_USERNAME or payload.password != VENDOR_PASSWORD:
        raise HTTPException(status_code=401, detail="Usuario o clave vendor incorrectos")
    token = create_access_token({"sub": VENDOR_USERNAME, "role": "vendor"})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"username": VENDOR_USERNAME, "name": VENDOR_NAME, "role": "vendor"},
        "product": PRODUCT_NAME,
        "copyright": COPYRIGHT,
    }


@router.get("/me")
def vendor_me(vendor=Depends(get_vendor)):
    st = license_status()
    return {
        **vendor,
        "instance_license": st,
        "seats": current_seats(),
        "copyright": COPYRIGHT,
    }


@router.get("/overview")
def vendor_overview(db: Session = Depends(get_db), vendor=Depends(get_vendor)):
    licenses = db.query(IssuedLicense).order_by(IssuedLicense.id.desc()).limit(100).all()
    users = db.query(User).order_by(User.name).all()
    key = load_stored_key()
    fp = license_fingerprint(key) if key else ""
    devices = []
    if fp:
        devices = (
            db.query(LicenseDevice)
            .filter(LicenseDevice.license_fp == fp)
            .order_by(LicenseDevice.last_seen.desc())
            .all()
        )
    return {
        "instance_license": license_status(),
        "licenses_issued": len(licenses),
        "shop_users": len(users),
        "devices_active": sum(1 for d in devices if d.active),
        "seats": current_seats() or DEFAULT_LICENSE_SEATS,
        "licenses": [
            {
                "id": x.id,
                "shop_name": x.shop_name,
                "seats": x.seats,
                "expires": x.expires,
                "note": x.note,
                "contact_name": x.contact_name,
                "contact_phone": x.contact_phone,
                "active": x.active,
                "created_at": x.created_at.isoformat() if x.created_at else None,
                "key_preview": (x.license_key[:18] + "…") if x.license_key else "",
                "license_key": x.license_key,
            }
            for x in licenses
        ],
        "users": [
            {"id": u.id, "name": u.name, "username": u.username, "role": u.role, "active": u.active}
            for u in users
        ],
        "devices": [
            {
                "id": d.id,
                "device_id": d.device_id,
                "device_name": d.device_name,
                "last_user": d.last_user,
                "active": d.active,
                "last_seen": d.last_seen.isoformat() if d.last_seen else None,
            }
            for d in devices
        ],
    }


@router.post("/licenses")
def vendor_create_license(payload: LicenseCreateIn, db: Session = Depends(get_db), vendor=Depends(get_vendor)):
    seats = payload.seats or DEFAULT_LICENSE_SEATS
    try:
        key = issue_license(payload.shop_name, payload.expires, seats=seats, note=payload.note)
        parse_license(key)  # validate
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    row = IssuedLicense(
        shop_name=payload.shop_name.strip(),
        license_key=key,
        seats=seats,
        expires=payload.expires,
        note=payload.note or "",
        contact_name=payload.contact_name or "",
        contact_phone=payload.contact_phone or "",
        active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    activated = False
    if payload.activate_here:
        save_license(key)
        activated = True
    return {
        "ok": True,
        "id": row.id,
        "shop_name": row.shop_name,
        "seats": row.seats,
        "expires": row.expires,
        "license_key": key,
        "activated_here": activated,
        "message": "Licencia creada. Entréguele la clave al taller (2 dispositivos por defecto).",
    }


@router.post("/users")
def vendor_create_shop_user(payload: ShopUserIn, db: Session = Depends(get_db), vendor=Depends(get_vendor)):
    if payload.role not in ("admin", "recepcion", "mecanico"):
        raise HTTPException(status_code=400, detail="Rol inválido")
    if db.query(User).filter(User.username == payload.username.strip().lower()).first():
        raise HTTPException(status_code=400, detail="Usuario ya existe")
    u = User(
        name=payload.name.strip(),
        username=payload.username.strip().lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return {"ok": True, "id": u.id, "username": u.username, "role": u.role, "name": u.name}


@router.post("/users/{user_id}/password")
def vendor_reset_password(
    user_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    vendor=Depends(get_vendor),
):
    pwd = (payload.get("password") or "").strip()
    if len(pwd) < 6:
        raise HTTPException(status_code=400, detail="Clave mínima 6 caracteres")
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    u.password_hash = hash_password(pwd)
    db.commit()
    return {"ok": True, "username": u.username}


@router.post("/devices/{device_row_id}/revoke")
def vendor_revoke_device(device_row_id: int, db: Session = Depends(get_db), vendor=Depends(get_vendor)):
    d = db.query(LicenseDevice).filter(LicenseDevice.id == device_row_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    d.active = False
    db.commit()
    return {"ok": True, "message": "Dispositivo liberado. El taller puede registrar otro."}


@router.post("/licenses/{license_id}/deactivate")
def vendor_deactivate_license(license_id: int, db: Session = Depends(get_db), vendor=Depends(get_vendor)):
    row = db.query(IssuedLicense).filter(IssuedLicense.id == license_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Licencia no encontrada")
    row.active = False
    db.commit()
    return {"ok": True}
