"""Cierre en colones con prueba — SINPE + WhatsApp + referencia OT/FE."""

from __future__ import annotations

from urllib.parse import quote_plus

from sqlalchemy.orm import Session, joinedload

from app.models import ElectronicInvoice, Reception, ShopSettings, Vehicle, WorkOrder
from app.services import get_settings

PROMISE = "Cierre en colones. Con prueba."


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
        PROMISE,
        "",
        f"Pago SINPE Móvil por ₡{amt}",
        f"Al número: {sinpe_phone}",
        f"A nombre de: {sinpe_name}",
        f"Referencia: {reference}",
    ]
    if plate:
        lines.append(f"Placa: {plate}")
    lines.append("")
    lines.append("Cuando pague, envíenos el comprobante. Katire · De la llave al XML.")
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

    if not inv and wo:
        inv = (
            db.query(ElectronicInvoice)
            .filter(ElectronicInvoice.work_order_id == wo.id)
            .order_by(ElectronicInvoice.id.desc())
            .first()
        )

    fe_clave = (inv.clave if inv else "") or ""
    fe_status = (getattr(inv, "hacienda_status", None) if inv else "") or (inv.status if inv else "") or ""

    proof = {
        "kind": "cierre_cobro",
        "promise": PROMISE,
        "reference": reference,
        "amount": round(amount, 2),
        "sinpe_phone": sinpe_phone,
        "sinpe_name": sinpe_name,
        "payment_status": getattr(wo, "payment_status", None) if wo else None,
        "fe_clave": fe_clave,
        "fe_status": fe_status,
        "plate": plate,
        "customer_name": customer_name,
        "print_path": f"/api/payments/cierre-proof?work_order_id={wo.id}" if wo else (
            f"/api/payments/cierre-proof?invoice_id={inv.id}" if inv else ""
        ),
    }

    return {
        "ok": True,
        "promise": PROMISE,
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
        "proof": proof,
        "fe_clave": fe_clave,
        "fe_status": fe_status,
    }


def cierre_proof_html(payload: dict) -> str:
    amt = f"{float(payload.get('amount') or 0):,.0f}".replace(",", ".")
    ref = payload.get("reference") or "—"
    status = payload.get("payment_status") or "pendiente"
    fe = payload.get("fe_clave") or "Pendiente de emitir"
    plate = payload.get("plate") or "—"
    name = payload.get("customer_name") or "Cliente"
    shop = payload.get("sinpe_name") or "Taller"
    phone = payload.get("sinpe_phone") or "—"
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"/>
<title>Katire — Cierre de cobro</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;600&display=swap');
body{{font-family:'DM Sans',system-ui,sans-serif;margin:0;padding:28px;background:#14110e;color:#f7f1ea}}
.card{{max-width:640px;margin:0 auto;background:#1c1814;border:1px solid #3a3228;border-radius:16px;padding:26px}}
.mark{{font-family:Syne,sans-serif;font-size:2rem;margin:0;letter-spacing:-.04em}}
.mark span{{color:#e8a54b}}
.pill{{display:inline-block;margin:12px 0;padding:.4rem .85rem;border-radius:999px;background:#e8a54b;color:#14110e;font-weight:800;font-size:.78rem}}
.row{{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid #2a241c}}
.k{{color:#9a8f82;font-size:.82rem}}.v{{font-weight:700}}
.amt{{font-size:2rem;font-weight:800;margin:14px 0 6px;color:#e8a54b}}
.fine{{font-size:.72rem;color:#7a7066;margin-top:18px}}
@media print{{body{{background:#fff;color:#111}}.card{{border-color:#ddd;background:#fff}}.amt,.mark span{{color:#b36b00}}.k,.fine{{color:#666}}}}
</style></head><body>
<div class="card">
  <p class="mark">Ka<span>tire</span></p>
  <div class="pill">{PROMISE}</div>
  <div class="amt">₡{amt}</div>
  <div class="row"><span class="k">Cliente</span><span class="v">{name}</span></div>
  <div class="row"><span class="k">Placa</span><span class="v">{plate}</span></div>
  <div class="row"><span class="k">Referencia</span><span class="v">{ref}</span></div>
  <div class="row"><span class="k">SINPE</span><span class="v">{phone} · {shop}</span></div>
  <div class="row"><span class="k">Estado cobro</span><span class="v">{status}</span></div>
  <div class="row"><span class="k">FE Hacienda</span><span class="v">{fe}</span></div>
  <p class="fine">Prueba de cierre Katire · De la llave al XML. · WhatsApp con monto y referencia = cobro accionable.</p>
</div>
<script>window.onload=()=>window.print()</script>
</body></html>"""
