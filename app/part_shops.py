"""Tiendas de repuestos CR + helpers de búsqueda / WhatsApp."""

from __future__ import annotations

from urllib.parse import quote_plus

from sqlalchemy.orm import Session

from app.models import Supplier

# Catálogo base: tiendas conocidas + plantilla de aliados (el taller completa datos)
DEFAULT_SHOPS = [
    {
        "name": "Repuestos Gigante",
        "kind": "tienda",
        "phone": "40330800",
        "whatsapp": "50687185353",
        "email": "mercadeo@repuestosgigante.com",
        "city": "Costa Rica",
        "website": "https://repuestosgigante.com/",
        "search_url": "https://repuestosgigante.com/?s={q}",
        "specialty": "Repuestos Toyota, Nissan, Hyundai, Suzuki, Kia",
        "notes": "Sucursales en todo el país · Liberia/Nicoya disponibles",
    },
    {
        "name": "Repuestos La Guaca (Guacamaya)",
        "kind": "tienda",
        "phone": "22171818",
        "whatsapp": "50671870541",
        "email": "info@laguaca.cr",
        "city": "Costa Rica",
        "website": "https://laguacaenlinea.cr/",
        "search_url": "https://laguacaenlinea.cr/?s={q}",
        "specialty": "Repuestos nuevos y usados · 17 sucursales",
        "notes": "Incluye Liberia y Santa Cruz",
    },
    {
        "name": "Aliado — Rectificación / cajas",
        "kind": "aliado",
        "phone": "",
        "whatsapp": "",
        "email": "",
        "city": "Guanacaste",
        "website": "",
        "search_url": "",
        "specialty": "Cajas de cambios, motores, rectificación",
        "notes": "Complete teléfono y WhatsApp del taller aliado real",
    },
]


def ensure_default_shops(db: Session) -> None:
    for row in DEFAULT_SHOPS:
        existing = db.query(Supplier).filter(Supplier.name == row["name"]).first()
        if existing:
            for key, value in row.items():
                if key == "name":
                    continue
                current = getattr(existing, key, None)
                if current in (None, "", "tienda") or (key != "kind" and not current):
                    setattr(existing, key, value)
            existing.active = True
        else:
            db.add(Supplier(**row))
    db.commit()


def shop_dict(s: Supplier) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "phone": s.phone or "",
        "email": s.email or "",
        "city": s.city or "",
        "notes": s.notes or "",
        "kind": s.kind or "tienda",
        "website": s.website or "",
        "whatsapp": s.whatsapp or "",
        "search_url": s.search_url or "",
        "specialty": s.specialty or "",
    }


def build_search_link(shop: Supplier, query: str) -> str:
    q = (query or "").strip()
    if shop.search_url and "{q}" in shop.search_url and q:
        return shop.search_url.replace("{q}", quote_plus(q))
    if shop.website:
        return shop.website
    if q:
        return f"https://www.google.com/search?q={quote_plus(q + ' ' + shop.name + ' Costa Rica')}"
    return ""


def build_whatsapp_order(shop: Supplier, query: str, vehicle: str = "") -> str:
    digits = "".join(ch for ch in (shop.whatsapp or shop.phone or "") if ch.isdigit())
    if digits and not digits.startswith("506") and len(digits) == 8:
        digits = "506" + digits
    if not digits:
        return ""
    msg = f"Hola {shop.name}, soy de Aitorepuestos. Necesito cotizar: {query}"
    if vehicle:
        msg += f" para {vehicle}"
    msg += ". ¿Tienen disponibilidad y precio?"
    return f"https://wa.me/{digits}?text={quote_plus(msg)}"
