"""Cobro SINPE Móvil + WhatsApp — cierra la plata del taller en CR."""

from __future__ import annotations

from urllib.parse import quote_plus

from sqlalchemy.orm import Session, joinedload

from app.models import ElectronicInvoice, Reception, ShopSettings, Vehicle, WorkOrder
from app.services import get_settings


def cr_digits(phone: str) -> str:
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if digits and not digits.startswith("506") and len(digits) == 8:
        digits = "506" + digits
    return digits


def sinpe_target(settings: ShopSettings) -> tuple[str, str]:
    """Teléfono SINPE y nombre a mostrar."""
    phone = (getattr(settings, "sinpe_phone", None) or "").strip() or (settings.whatsapp or settings.phone or "")
    name = (getattr(settings, "sinpe_name", None) or "").strip() or (settings.shop_name or "Aitorepuestos")
    return phone, name


def build_sinpe_message(
    *,
    amount: float,
    reference: str,
    sinpe_phone: str,
    sinpe_name: str,
    customer_name: str = "",
    plate: str = "",
) -> str:
    amt = f"{amount:,.0f}".replace(",", ".")
    lines = [
        f"Hola{(' ' + customer_name) if customer_name else ''},",
        f"Pago SINPE Móvil por ₡{amt}",
        f"Al número: {sinpe_phone}",
        f"A nombre de: {sinpe_name}",
        f"Referencia: {reference}",
    ]
    if plate:
        lines.append(f"Placa: {plate}")
    lines.append("Cuando pague, avísenos con el comprobante. ¡Gracias!")
    return "\n".join(lines)


def build_wa_url(customer_phone: str, message: str) -> str:
    digits = cr_digits(customer_phone)
    if not digits:
        return ""
    return f"https://wa.me/{digits}?text={quote_plus(message)}"


def create_sinpe_link(
    db: Session,
    *,
    work_order_id: int | None = None,
    invoice_id: int | None = None,
    mark_sent: bool = True,
) -> dict:
    settings = get_settings(db)
    sinpe_phone, sinpe_name = sinpe_target(settings)
    if not cr_digits(sinpe_phone):
        return {
            "ok": False,
            "error": "Configure el teléfono SINPE en Casa (sinpe_phone).",
            "needs_setup": True,
        }

    amount = 0.0
    reference = ""
    customer_name = ""
    customer_phone = ""
    plate = ""
    wo: WorkOrder | None = None
    inv: ElectronicInvoice | None = None

    wo_load = joinedload(WorkOrder.reception).joinedload(Reception.vehicle).joinedload(Vehicle.customer)

    if invoice_id:
        inv = db.query(ElectronicInvoice).filter(ElectronicInvoice.id == invoice_id).first()
        if not inv:
            return {"ok": False, "error": "Comprobante no encontrado"}
        amount = float(inv.total_comprobante or 0)
        reference = f"FE-{(inv.clave or str(inv.id))[:12]}"
        if inv.work_order_id:
            wo = db.query(WorkOrder).options(wo_load).filter(WorkOrder.id == inv.work_order_id).first()
    elif work_order_id:
        wo = db.query(WorkOrder).options(wo_load).filter(WorkOrder.id == work_order_id).first()
        if not wo:
            return {"ok": False, "error": "Orden no encontrada"}
        amount = float(wo.grand_total or 0)
        reference = wo.code or f"OT-{wo.id}"
    else:
        return {"ok": False, "error": "Indique work_order_id o invoice_id"}

    if wo and wo.reception:
        veh = wo.reception.vehicle
        if veh:
            plate = veh.plate or ""
            cust = veh.customer
            if cust:
                customer_name = cust.name or ""
                customer_phone = cust.phone or ""
        if not reference:
            reference = wo.code

    if amount <= 0:
        return {"ok": False, "error": "El monto a cobrar es ₡0 — agregue líneas a la OT"}

    message = build_sinpe_message(
        amount=amount,
        reference=reference,
        sinpe_phone=sinpe_phone,
        sinpe_name=sinpe_name,
        customer_name=customer_name,
        plate=plate,
    )
    wa_url = build_wa_url(customer_phone, message)

    if mark_sent and wo and getattr(wo, "payment_status", "pendiente") != "pagado":
        wo.payment_status = "sinpe_enviado"
        db.commit()

    return {
        "ok": True,
        "wa_url": wa_url,
        "message": message,
        "reference": reference,
        "amount": round(amount, 2),
        "sinpe_phone": sinpe_phone,
        "sinpe_name": sinpe_name,
        "customer_phone": customer_phone,
        "customer_name": customer_name,
        "plate": plate,
        "work_order_id": wo.id if wo else None,
        "invoice_id": inv.id if inv else None,
        "payment_status": getattr(wo, "payment_status", None) if wo else None,
        "needs_customer_phone": not bool(wa_url),
    }
