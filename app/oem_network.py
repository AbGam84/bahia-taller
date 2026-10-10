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


_BRAND_CANON = {
    "toyota": "Toyota",
    "nissan": "Nissan",
    "hyundai": "Hyundai",
    "kia": "Kia",
    "suzuki": "Suzuki",
    "honda": "Honda",
    "mazda": "Mazda",
    "mitsubishi": "Mitsubishi",
    "chevrolet": "Chevrolet",
    "chevy": "Chevrolet",
    "ford": "Ford",
    "volkswagen": "Volkswagen",
    "vw": "Volkswagen",
    "isuzu": "Isuzu",
    "great wall": "Great Wall",
    "byd": "BYD",
}


def normalize_brand(brand: str) -> str:
    b = (brand or "").strip()
    if not b:
        return ""
    key = _norm(b)
    return _BRAND_CANON.get(key, b[:1].upper() + b[1:] if b else "")


def match_oem_profile(brand: str, model: str, year: int = 0) -> dict | None:
    brand = normalize_brand(brand)
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
        if year and (year < y_min - 2 or year > y_max + 2):
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
    part_hint: str = "",
    vin_hint: str = "",
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

    ref = parts_reference_by_plate(db, tenant_id, plate_norm, brand_hint, model_hint, year_hint)
    vehicle = ref.get("vehicle")
    registered = bool(ref.get("found_vehicle"))
    brand = normalize_brand(brand_hint or (vehicle.get("brand") if vehicle else "") or "")
    model = (model_hint or (vehicle.get("model") if vehicle else "") or "").strip()
    year = 0
    if year_hint and str(year_hint).isdigit():
        year = int(year_hint)
    elif vehicle and vehicle.get("year"):
        year = int(vehicle.get("year") or 0)

    vin_raw = (vin_hint or "").strip().upper()
    if not vin_raw and vehicle and (vehicle.get("vin") or "").strip():
        vin_raw = (vehicle.get("vin") or "").strip().upper()

    vin_decode = {}
    if len(vin_raw) >= 11:
        vin_decode = decode_vin_nhtsa(vin_raw)
        if vin_decode.get("make") and not brand_hint:
            brand = normalize_brand(vin_decode.get("make") or brand)
        if vin_decode.get("model") and not model_hint:
            model = (vin_decode.get("model") or model).strip()
        vy = vin_decode.get("model_year") or ""
        if str(vy).isdigit() and not year_hint:
            year = int(vy)

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
        specs.update(
            {
                "placa": plate_norm,
                "marca": brand,
                "modelo": model,
                "año": year or year_hint,
                "vin_consulta": vin_raw or "",
            }
        )

    if vin_decode:
        specs["vin_decodificado"] = vin_decode
    elif vin_raw:
        specs["vin_registrado"] = vin_raw

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
                    "part_info": "Pieza original OEM de fábrica (catálogo CR)",
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

    search_text = (part_hint or "").strip() or f"{brand} {model}".strip() or f"repuestos vehículo {plate_norm}"
    intro: list[dict] = []
    guaca = next((s for s in shops if "guaca" in (s.name or "").lower()), None)
    if guaca:
        url = build_search_link(guaca, search_text, plate_norm)
        if url:
            intro.append({"label": "La Guaca en línea", "url": url})
    gigante_q = f"site:repuestosgigante.com {brand} {model} repuesto".strip() or f"site:repuestosgigante.com {plate_norm}"
    intro.append(
        {
            "label": "Repuestos Gigante (web)",
            "url": f"https://www.google.com/search?q={quote_plus(gigante_q)}",
        }
    )
    intro.append(
        {
            "label": "Google código / pieza",
            "url": f"https://www.google.com/search?q={quote_plus(f'{search_text} {plate_norm} Costa Rica OEM')}",
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
    from app.tecdoc_client import enrich_parts, tecdoc_configured
    from app.universal_parts import (
        group_parts_by_system,
        merge_oem_lists,
        overlay_factory_oem,
        universal_parts_for_vehicle,
    )

    tecdoc_meta: dict = {}
    try:
        if tecdoc_configured():
            tec_parts, tecdoc_meta = enrich_parts(
                brand=brand,
                model=model,
                year=year,
                vin=vin_raw or (vehicle.get("vin") if vehicle else "") or "",
                part_hint=(part_hint or "").strip(),
            )
            for row in tec_parts:
                code = row.get("oem_code") or ""
                name = row.get("name") or ""
                row["network_links"] = network_links_for_part(code, name, brand, model, year_str, shops)
                oem_parts.append(row)
        else:
            from app.tecdoc_client import tecdoc_status

            tecdoc_meta = {"tecdoc": tecdoc_status()}
    except Exception:
        from app.tecdoc_client import tecdoc_status

        tecdoc_meta = {"tecdoc": tecdoc_status()}

    existing_names = {_norm(p.get("name") or "") for p in oem_parts}
    universal = universal_parts_for_vehicle(
        brand,
        model,
        year_str,
        plate=plate_norm,
        part_hint=(part_hint or "").strip(),
        existing_names=existing_names,
        network_links_fn=lambda code, name, b, m, y: network_links_for_part(
            code, name, b, m, y, shops
        ),
    )
    if universal:
        oem_parts = merge_oem_lists(oem_parts, universal)
    oem_parts = overlay_factory_oem(oem_parts, profile)

    from app.part_shops import build_whatsapp_order
    from app.services import get_settings

    settings = get_settings(db, tenant_id)
    shop_label = settings.shop_name or "el taller"
    veh_whatsapp = f"{plate_norm} {brand} {model}".strip()
    shop_cards = []
    for s in shops:
        item = shop_dict(s)
        item["search_link"] = build_search_link(s, search_text, plate_norm)
        item["whatsapp_link"] = build_whatsapp_order(s, search_text, veh_whatsapp, from_shop=shop_label)
        shop_cards.append(item)

    oem_with_code = sum(
        1
        for p in oem_parts
        if (p.get("oem_code") or "").strip()
        and "consultar oem" not in (p.get("oem_code") or "").lower()
        and p.get("oem_code") != "—"
    )
    universal_count = sum(1 for p in oem_parts if p.get("source") == "catalogo_universal")

    sys_n = len(group_parts_by_system(oem_parts))
    if not registered and not brand and not model:
        result_message = (
            f"Placa {plate_norm} (sin registro): {sys_n} sistemas, {len(oem_parts)} componentes del vehículo. "
            "Marca, modelo, año o VIN → códigos OEM originales de fábrica en cada pieza."
        )
    elif not registered:
        result_message = (
            f"Consulta sin registro · placa {plate_norm} · {brand} {model} {year_str}. "
            f"{oem_with_code} códigos OEM de fábrica en {len(oem_parts)} piezas listadas."
        )
    elif not brand and not model:
        result_message = (
            f"{len(oem_parts)} tipos de repuesto — complete marca/modelo/año o VIN para OEM exactos."
        )
    elif not oem_parts:
        result_message = "Sin filas — limpie el filtro «Repuesto» o escriba otro término."
    else:
        result_message = (
            f"{len(oem_parts)} repuestos listados ({oem_with_code} con código OEM, "
            f"{universal_count} tipos universales). Use el filtro para buscar pieza."
        )

    if tecdoc_meta.get("tecdoc", {}).get("configured"):
        result["disclaimer"] = (
            "Catálogo local (GAM San José / Alajuela) + TecDoc cuando hay licencia activa. "
            "Confirme códigos OEM con VIN/motor antes de comprar."
        )
    else:
        result["disclaimer"] = (
            "Catálogo de referencia Costa Rica (San José, Alajuela y nacional). "
            "Para catálogo OEM completo active TecDoc (TECDOC_API_KEY en servidor)."
        )

    result["registered_in_shop"] = registered
    result["guest_consult"] = not registered
    result["vehicle_systems"] = group_parts_by_system(oem_parts)
    result["oem_parts"] = oem_parts
    result["oem_parts_count"] = len(oem_parts)
    result["oem_coded_count"] = oem_with_code
    result["history_parts"] = ref.get("history_parts") or []
    result["network_intro"] = intro
    result["shops"] = shop_cards
    result["message"] = result_message
    result["tecdoc"] = tecdoc_meta.get("tecdoc") or {"configured": False}
    result["tecdoc_vehicle"] = tecdoc_meta.get("tecdoc_vehicle")
    return result
