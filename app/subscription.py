"""Licencia mensual Katire — extender al registrar pago."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.license import issue_license, license_fingerprint, parse_license
from app.models import IssuedLicense, LicenseDevice, Tenant


def _days_in_month(year: int, month: int) -> int:
    if month == 2:
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        return 29 if leap else 28
    return (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[month - 1]


def add_months(start: date, months: int) -> date:
    months = max(0, int(months))
    if months == 0:
        return start
    m = start.month - 1 + months
    y = start.year + m // 12
    m = m % 12 + 1
    day = min(start.day, _days_in_month(y, m))
    return date(y, m, day)


def expiry_from_months(months: int, *, from_day: date | None = None) -> str:
    base = from_day or date.today()
    return add_months(base, months).isoformat()


def _current_expiry_row(row: IssuedLicense) -> date:
    exp = (row.expires or "").strip()
    if exp:
        try:
            return datetime.strptime(exp[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    key = (row.license_key or "").strip()
    if key:
        try:
            data = parse_license(key)
            return datetime.strptime(str(data["exp"]), "%Y-%m-%d").date()
        except ValueError:
            pass
    return date.today()


def renew_issued_license(db: Session, row: IssuedLicense, months: int = 1) -> dict:
    """Registra pago: nueva clave KT1 con vencimiento extendido y taller activo al instante."""
    if not row.active:
        row.active = True
    months = max(1, min(int(months), 36))
    today = date.today()
    cur = _current_expiry_row(row)
    base = cur if cur >= today else today
    new_exp = add_months(base, months)
    old_key = (row.license_key or "").strip()
    old_fp = license_fingerprint(old_key) if old_key else ""

    note = (row.note or "").strip()
    if "mensual" not in note.lower():
        note = (note + " · Plan mensual").strip(" ·")

    new_key = issue_license(
        row.shop_name,
        new_exp.isoformat(),
        seats=int(row.seats or 2),
        note=note,
    )
    parse_license(new_key)
    new_fp = license_fingerprint(new_key)

    row.license_key = new_key
    row.expires = new_exp.isoformat()
    row.note = note
    row.last_paid_at = datetime.utcnow()
    row.paid_months_total = int(row.paid_months_total or 0) + months

    tenant = None
    if old_fp:
        tenant = db.query(Tenant).filter(Tenant.license_fp == old_fp).first()
    if not tenant:
        tenant = (
            db.query(Tenant)
            .filter(Tenant.name == row.shop_name, Tenant.active.is_(True))
            .order_by(Tenant.id.desc())
            .first()
        )

    if tenant:
        tenant.license_key = new_key
        tenant.license_fp = new_fp
        tenant.expires = new_exp.isoformat()
        tenant.active = True
        tenant.seats = int(row.seats or tenant.seats or 2)
        if row.monthly_fee_crc:
            tenant.monthly_fee_crc = int(row.monthly_fee_crc)

    if old_fp and old_fp != new_fp:
        for dev in db.query(LicenseDevice).filter(LicenseDevice.license_fp == old_fp).all():
            dev.license_fp = new_fp

    db.commit()
    db.refresh(row)
    return {
        "license_id": row.id,
        "shop_name": row.shop_name,
        "expires": row.expires,
        "paid_until": row.expires,
        "license_key": new_key,
        "activation_url": f"/activar?key={new_key}",
        "tenant_code": tenant.code if tenant else None,
        "tenant_updated": tenant is not None,
        "months_added": months,
        "message": (
            f"Pago registrado: +{months} mes(es). Válido hasta {row.expires}. "
            + ("El taller puede seguir entrando con el mismo usuario — la licencia ya está actualizada en servidor."
               if tenant
               else "Envíe el link de activación si el taller aún no instaló.")
        ),
    }
