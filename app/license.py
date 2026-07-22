"""Licencia comercial Katire — solo el vendor emite claves para talleres."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import date, datetime
from pathlib import Path

from app.config import DATA_DIR, IS_PRODUCTION, LICENSE_KEY, LICENSE_SECRET, SHOP_LICENSE_NAME

LICENSE_FILE = DATA_DIR / "license.json"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _sign(payload_b64: str, secret: str) -> str:
    dig = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    return _b64url(dig)


def issue_license(
    shop_name: str,
    expires: str,
    seats: int = 2,
    note: str = "",
    secret: str | None = None,
) -> str:
    """Genera clave KT1.<payload>.<sig> (solo scripts internos del vendor)."""
    secret = secret or LICENSE_SECRET
    if not secret or secret == "change-me":
        raise ValueError("Defina KATIRE_LICENSE_SECRET antes de emitir licencias")
    payload = {
        "v": 1,
        "shop": shop_name.strip(),
        "exp": expires,  # YYYY-MM-DD
        "seats": int(seats),
        "note": note or "",
        "issued": date.today().isoformat(),
    }
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    sig = _sign(payload_b64, secret)
    return f"KT1.{payload_b64}.{sig}"


def parse_license(key: str, secret: str | None = None) -> dict:
    secret = secret or LICENSE_SECRET
    key = (key or "").strip()
    if not key.startswith("KT1."):
        raise ValueError("Formato de licencia inválido")
    parts = key.split(".")
    if len(parts) != 3:
        raise ValueError("Licencia incompleta")
    _, payload_b64, sig = parts
    expect = _sign(payload_b64, secret)
    if not hmac.compare_digest(expect, sig):
        raise ValueError("Firma de licencia inválida")
    data = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    exp = datetime.strptime(data["exp"], "%Y-%m-%d").date()
    if exp < date.today():
        raise ValueError(f"Licencia vencida el {data['exp']}")
    return data


def save_license(key: str) -> dict:
    data = parse_license(key)
    LICENSE_FILE.write_text(
        json.dumps({"key": key, "parsed": data, "activated_at": datetime.utcnow().isoformat() + "Z"}, indent=2),
        encoding="utf-8",
    )
    return data


def load_stored_key() -> str:
    if LICENSE_KEY:
        return LICENSE_KEY
    if LICENSE_FILE.exists():
        try:
            return json.loads(LICENSE_FILE.read_text(encoding="utf-8")).get("key") or ""
        except Exception:
            return ""
    return ""


def license_status() -> dict:
    """Estado para health / pantalla de activación."""
    key = load_stored_key()
    if not key:
        # En desarrollo local sin clave: modo libre (no bloquea)
        if not IS_PRODUCTION:
            return {
                "ok": True,
                "mode": "development",
                "message": "Desarrollo local sin licencia (no usar para entrega al taller)",
                "shop": SHOP_LICENSE_NAME or "Dev",
                "expires": None,
                "seats": 99,
            }
        return {
            "ok": False,
            "mode": "unlicensed",
            "message": "Producto no activado. Contacte a Katire para su licencia.",
            "shop": None,
            "expires": None,
            "seats": 0,
        }
    try:
        data = parse_license(key)
        return {
            "ok": True,
            "mode": "licensed",
            "message": "Licencia Katire activa",
            "shop": data.get("shop"),
            "expires": data.get("exp"),
            "seats": data.get("seats", 1),
            "note": data.get("note") or "",
        }
    except ValueError as exc:
        return {
            "ok": False,
            "mode": "invalid",
            "message": str(exc),
            "shop": None,
            "expires": None,
            "seats": 0,
        }


def license_fingerprint(key: str) -> str:
    return hashlib.sha256((key or "").encode("utf-8")).hexdigest()[:40]


def current_seats() -> int:
    st = license_status()
    if not st.get("ok"):
        return 0
    try:
        return int(st.get("seats") or 2)
    except Exception:
        return 2


def register_device(
    db,
    device_id: str,
    device_name: str = "",
    username: str = "",
    *,
    license_key: str | None = None,
    seats: int | None = None,
) -> dict:
    """Registra o actualiza un dispositivo. Máximo `seats` activos por licencia (por taller)."""
    from app.models import LicenseDevice

    device_id = (device_id or "").strip()
    if not device_id:
        raise ValueError("Falta identificador de dispositivo")
    key = (license_key or "").strip() or load_stored_key()
    if not key:
        if not IS_PRODUCTION:
            return {"ok": True, "mode": "development", "seats": 99, "used": 0}
        raise ValueError("Sin licencia activa")
    fp = license_fingerprint(key)
    if seats is None:
        seats = current_seats() or 2
    seats = int(seats or 2)
    existing = (
        db.query(LicenseDevice)
        .filter(LicenseDevice.license_fp == fp, LicenseDevice.device_id == device_id)
        .first()
    )
    if existing:
        existing.active = True
        existing.last_seen = datetime.utcnow()
        existing.last_user = username or existing.last_user
        if device_name:
            existing.device_name = device_name
        db.commit()
        used = db.query(LicenseDevice).filter(LicenseDevice.license_fp == fp, LicenseDevice.active.is_(True)).count()
        return {"ok": True, "seats": seats, "used": used, "device_id": device_id}

    used = db.query(LicenseDevice).filter(LicenseDevice.license_fp == fp, LicenseDevice.active.is_(True)).count()
    if used >= seats:
        raise ValueError(
            f"Límite de {seats} dispositivos alcanzado. Pida al proveedor Katire liberar un equipo o ampliar la licencia."
        )
    row = LicenseDevice(
        license_fp=fp,
        device_id=device_id,
        device_name=device_name or "Dispositivo",
        last_user=username or "",
        active=True,
    )
    db.add(row)
    db.commit()
    return {"ok": True, "seats": seats, "used": used + 1, "device_id": device_id}


def require_license_ok() -> None:
    st = license_status()
    if not st.get("ok"):
        from fastapi import HTTPException

        raise HTTPException(status_code=402, detail=st.get("message") or "Licencia requerida")
