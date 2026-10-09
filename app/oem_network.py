"""Ficha vehículo + códigos OEM de referencia + enlaces a red de repuesteras."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy.orm import Session

from app.models import Reception
from app.part_shops import build_search_link, ensure_default_shops
from app.models import Supplier

CATALOG_PATH = Path(__file__).resolve().parent / "catalog" / "vehicle_oem_catalog.json"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


@lru_cache(maxsize=1)
def _load_catalog() -> dict:
    if not CATALOG_PATH.is_file():
        return {"profiles": []}
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def match_oem_profile(brand: str, model: str, year: int = 0) -> dict | None:
    b = _norm(brand)
    m = _norm(model)
    if not b or not m:
        return None
    best = None
    best_score = 0
    for profile in _load_catalog().get("profiles") or []:
        if _norm(profile.get("brand") or "") != b:
            continue
        models = [_norm(x) for x in profile.get("models") or []]
        if not any(m == pm or pm in m or m in pm for pm in models):
            continue
        y_min = int(profile.get("year_min") or 0)
        y_max = int(profile.get("year_max") or 9999)
        if year and (year < y_min or year > y_max):
            continue
        score = 2 + (1 if year and y_min <= year <= y_max else 0)
        if score > best_score:
            best_score = score
            best = profile
    return best


def decode_vin_nhtsa(vin: str) -> dict:
    """Decodifica VIN vía NHTSA (útil en imports; no cubre todos los CR)."""
    vin = (vin or "").strip().upper()
    if len(vin) < 11:
        return {}
    try:
        import urllib.request

        url = f"https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{quote_plus(vin)}?format=json"
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}
    results = {r.get("Variable"): r.get("Value") for r in data.get("Results") or [] if r.get("Value")}
    return {
        "make": results.get("Make") or "",
        "model": results.get("Model") or "",
        "model_year": results.get("Model Year") or "",
        "displacement_l": results.get("Displacement (L)") or "",
        "engine_cylinders": results.get("Engine Number of Cylinders") or "",
        "fuel": results.get("Fuel Type - Primary") or "",
        "drive": results.get("Drive Type") or "",
        "body": results.get("Body Class") or "",
        "plant": results.get("Plant Country") or "",
    }


def network_links_for_part(
    oem_code: str,
    part_name: str,
    brand: str,
    model: str,
    year: str,
    shops: list[Supplier] | None = None,
) -> list[dict]:
    """Enlaces para verificar/comprar el código OEM en la red."""
    veh = " ".join(x for x in [brand, model, year] if x).strip()
    q_oem = f"{oem_code} {brand} {part_name}".strip()
    q_name = f"{part_name} {veh} OEM".strip()
    links: list[dict] = [
        {
            "label": "Google código OEM",
            "url": f"https://www.google.com/search?q={quote_plus(q_oem)}",
        },
        {
            "label": "Google pieza + vehículo",
            "url": f"https://www.google.com/search?q={quote_plus(q_name)}",
        },
    ]
    for shop in shops or []:
        if shop.kind != "tienda":
            continue
        url = build_search_link(shop, oem_code or part_name, veh)
        if url:
            links.append({"label": shop.name, "url": url})
    return links[:6]


def vehicle_technical_dossier(
    db: Session,
    tenant_id: int,
    plate: str,
    brand_hint: str = "",
    model_hint: str = "",
    year_hint: str = "",
) -> dict:
    from app.pro import parts_reference_by_plate
    from app.part_shops import shop_dict

    plate_norm = (plate or "").upper().strip()
    empty = {
        "plate": plate_norm,
        "found_vehicle": False,
        "vehicle": None,
        "specifications": {},
        "oem_parts": [],
        "catalog_match": None,
        "network_intro": [],
        "disclaimer": (
            "Lista de referencia OEM de mantenimiento frecuente. "
            "El catálogo completo de fábrica (todas las piezas del vehículo) "
            "requiere motor/VIN exacto e integración profesional (TecDoc / OEM). "
            "Use los enlaces para confirmar en la red."
        ),
    }
    if len(plate_norm.replace("-", "")) < 3:
        empty["error"] = "Placa muy corta"
        return empty

    ref = parts_reference_by_plate(db, tenant_id, plate_norm, brand_hint, model_hint)
    vehicle = ref.get("vehicle")
    brand = brand_hint or (vehicle.get("brand") if vehicle else "") or ""
    model = model_hint or (vehicle.get("model") if vehicle else "") or ""
    year = 0
    if year_hint and str(year_hint).isdigit():
        year = int(year_hint)
    elif vehicle and vehicle.get("year"):
        year = int(vehicle.get("year") or 0)

    vin_decode = {}
    if vehicle and (vehicle.get("vin") or "").strip():
        vin_decode = decode_vin_nhtsa(vehicle.get("vin") or "")

    profile = match_oem_profile(brand, model, year)
    specs = dict(profile.get("specs") or {}) if profile else {}
    if vehicle:
        specs.update(
            {
                "placa": plate_norm,
                "marca": vehicle.get("brand") or brand,
                "modelo": vehicle.get("model") or model,
                "año": vehicle.get("year") or year or "",
                "color": vehicle.get("color") or "",
                "vin_registrado": vehicle.get("vin") or "",
            }
        )
        if vehicle.get("customer"):
            specs["cliente"] = vehicle["customer"].get("name") or ""
    else:
        specs.update({"placa": plate_norm, "marca": brand, "modelo": model, "año": year or year_hint})

    if vin_decode:
        specs["vin_decodificado"] = vin_decode

    last_km = 0
    if vehicle and vehicle.get("id"):
        last_rec = (
            db.query(Reception)
            .filter(Reception.vehicle_id == vehicle["id"], Reception.tenant_id == tenant_id)
            .order_by(Reception.created_at.desc())
            .first()
        )
        if last_rec:
            last_km = last_rec.odometer_km or 0
    if last_km:
        specs["ultimo_km_taller"] = last_km

    ensure_default_shops(db, tenant_id)
    shops = (
        db.query(Supplier)
        .filter(Supplier.active.is_(True), Supplier.kind == "tienda", Supplier.tenant_id == tenant_id)
        .order_by(Supplier.name)
        .all()
    )

    oem_parts: list[dict] = []
    year_str = str(year or year_hint or "")
    if profile:
        for row in profile.get("parts") or []:
            code = (row.get("oem_code") or "").strip()
            name = (row.get("name") or "").strip()
            oem_parts.append(
                {
                    "category": row.get("category") or "General",
                    "name": name,
                    "oem_code": code,
                    "source": "catalogo_referencia",
                    "network_links": network_links_for_part(code, name, brand, model, year_str, shops),
                }
            )

    hist_by_code: dict[str, dict] = {}
    for h in ref.get("history_parts") or []:
        key = (h.get("name") or "").lower()
        if key and key not in hist_by_code:
            hist_by_code[key] = h

    for h in hist_by_code.values():
        oem_parts.append(
            {
                "category": "Historial taller",
                "name": h.get("name") or "",
                "oem_code": h.get("sku") or "—",
                "source": "historial_ot",
                "times_used": h.get("times_used"),
                "network_links": network_links_for_part(
                    h.get("sku") or "",
                    h.get("name") or "",
                    brand,
                    model,
                    year_str,
                    shops,
                ),
            }
        )

    intro: list[dict] = []
    guaca = next((s for s in shops if "guaca" in (s.name or "").lower()), None)
    if guaca:
        url = build_search_link(guaca, f"{brand} {model} repuestos", plate_norm)
        if url:
            intro.append({"label": "La Guaca en línea", "url": url})
    if brand or model:
        intro.append(
            {
                "label": "Repuestos Gigante (web)",
                "url": f"https://www.google.com/search?q={quote_plus(f'site:repuestosgigante.com {brand} {model} repuesto')}",
            }
        )

    result = dict(empty)
    result["found_vehicle"] = bool(ref.get("found_vehicle"))
    result["vehicle"] = vehicle
    result["visits_count"] = ref.get("visits_count") or 0
    result["specifications"] = specs
    result["catalog_match"] = (
        {
            "brand": profile.get("brand"),
            "models": profile.get("models"),
            "year_min": profile.get("year_min"),
            "year_max": profile.get("year_max"),
        }
        if profile
        else None
    )
    result["oem_parts"] = oem_parts
    result["network_intro"] = intro
    result["shops"] = [shop_dict(s) for s in shops]
    return result
