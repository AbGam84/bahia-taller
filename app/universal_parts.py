"""Tipos de repuesto para cualquier vehículo — referencia + búsqueda OEM en red."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

COMPONENTS_PATH = Path(__file__).resolve().parent / "catalog" / "vehicle_components.json"

# Sistemas y piezas habituales (cualquier marca). OEM exacto viene de catálogo CR, TecDoc o VIN.
UNIVERSAL_PART_TYPES: list[tuple[str, str]] = [
    ("Motor", "Filtro de aceite"),
    ("Motor", "Filtro de aire"),
    ("Motor", "Filtro de combustible"),
    ("Motor", "Bujías (juego)"),
    ("Motor", "Bobina de encendido"),
    ("Motor", "Cable bujía"),
    ("Motor", "Correa de accesorios"),
    ("Motor", "Tensor correa accesorios"),
    ("Motor", "Correa de distribución"),
    ("Motor", "Kit distribución"),
    ("Motor", "Bomba de agua"),
    ("Motor", "Termostato"),
    ("Motor", "Radiador"),
    ("Motor", "Manguera radiador superior"),
    ("Motor", "Manguera radiator inferior"),
    ("Motor", "Tapa radiador"),
    ("Motor", "Depósito refrigerante"),
    ("Motor", "Sensor temperatura"),
    ("Motor", "Sensor MAP / MAF"),
    ("Motor", "Sensor oxígeno (lambda)"),
    ("Motor", "Inyectores"),
    ("Motor", "Bomba de combustible"),
    ("Motor", "Cuerpo de aceleración"),
    ("Motor", "Junta tapa válvulas"),
    ("Motor", "Junta múltiple admisión"),
    ("Motor", "Junta múltiple escape"),
    ("Motor", "Soporte motor"),
    ("Motor", "Aceite motor (especificación)"),
    ("Frenos", "Pastillas freno delanteras"),
    ("Frenos", "Pastillas freno traseras"),
    ("Frenos", "Discos freno delanteros"),
    ("Frenos", "Discos freno traseros"),
    ("Frenos", "Zapatas freno traseras"),
    ("Frenos", "Tambor freno trasero"),
    ("Frenos", "Líquido de frenos"),
    ("Frenos", "Caliper delantero"),
    ("Frenos", "Caliper trasero"),
    ("Frenos", "Manguera freno"),
    ("Frenos", "Bomba de freno"),
    ("Frenos", "Booster / servofreno"),
    ("Frenos", "Sensor ABS"),
    ("Suspensión", "Amortiguador delantero"),
    ("Suspensión", "Amortiguador trasero"),
    ("Suspensión", "Resorte / espiral delantero"),
    ("Suspensión", "Resorte / espiral trasero"),
    ("Suspensión", "Buje barra estabilizadora"),
    ("Suspensión", "Link estabilizadora"),
    ("Suspensión", "Rotula"),
    ("Suspensión", "Terminal dirección"),
    ("Suspensión", "Brazo control / meseta"),
    ("Suspensión", "Buje brazo"),
    ("Suspensión", "Punta eje"),
    ("Suspensión", "Rodamiento rueda delantero"),
    ("Suspensión", "Rodamiento rueda trasero"),
    ("Dirección", "Bomba dirección hidráulica"),
    ("Dirección", "Cremallera dirección"),
    ("Dirección", "Líquido dirección"),
    ("Dirección", "Columna dirección"),
    ("Transmisión", "Embrague kit completo"),
    ("Transmisión", "Disco embrague"),
    ("Transmisión", "Plato presión"),
    ("Transmisión", "Collarin / bearing"),
    ("Transmisión", "Aceite caja manual"),
    ("Transmisión", "Filtro caja automática"),
    ("Transmisión", "Aceite caja automática"),
    ("Transmisión", "Semi-eje"),
    ("Transmisión", "Homocinética"),
    ("Transmisión", "Fuelle homocinética"),
    ("Transmisión", "Soporte caja"),
    ("Climatización", "Filtro cabina / polen"),
    ("Climatización", "Compresor A/C"),
    ("Climatización", "Condensador A/C"),
    ("Climatización", "Evaporador A/C"),
    ("Climatización", "Gas refrigerante"),
    ("Eléctrico", "Batería"),
    ("Eléctrico", "Alternador"),
    ("Eléctrico", "Motor arranque"),
    ("Eléctrico", "Foco delantero"),
    ("Eléctrico", "Foco trasero"),
    ("Eléctrico", "Bulbo intermitente"),
    ("Eléctrico", "Relay"),
    ("Eléctrico", "Fusible caja"),
    ("Eléctrico", "Sensor reversa"),
    ("Eléctrico", "Limpiaparabrisas motor"),
    ("Eléctrico", "Plumilla / escobilla"),
    ("Escape", "Silenciador"),
    ("Escape", "Catalizador"),
    ("Escape", "Sensor oxígeno escape"),
    ("Escape", "Junta múltiple escape"),
    ("Carrocería", "Parabrisas"),
    ("Carrocería", "Espejo retrovisor"),
    ("Carrocería", "Manija puerta exterior"),
    ("Carrocería", "Cerradura puerta"),
    ("Carrocería", "Bisagra capó"),
    ("Carrocería", "Amortiguador portón"),
    ("Llantas", "Neumático (medida según rin)"),
    ("Llantas", "Válvula rin"),
    ("Llantas", "Tapa válvula"),
    ("Motor", "Válvula PCV"),
    ("Motor", "Filtro breather"),
    ("Motor", "Polea cigüeñal"),
    ("Frenos", "Pastilla freno de mano"),
    ("Suspensión", "Barra estabilizadora"),
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


@lru_cache(maxsize=1)
def _load_component_systems() -> list[tuple[str, str]]:
    """(sistema, componente) desde JSON; fallback a lista legacy."""
    if COMPONENTS_PATH.is_file():
        data = json.loads(COMPONENTS_PATH.read_text(encoding="utf-8"))
        rows: list[tuple[str, str]] = []
        for block in data.get("systems") or []:
            sys_name = (block.get("name") or "General").strip()
            for comp in block.get("components") or []:
                name = (comp or "").strip()
                if name:
                    rows.append((sys_name, name))
        if rows:
            return rows
    return list(UNIVERSAL_PART_TYPES)


def group_parts_by_system(parts: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for p in parts:
        sys_name = (p.get("category") or "General").strip()
        if sys_name not in groups:
            groups[sys_name] = []
            order.append(sys_name)
        groups[sys_name].append(p)
    return [
        {"system": name, "count": len(groups[name]), "parts": groups[name]}
        for name in order
    ]


def universal_parts_for_vehicle(
    brand: str,
    model: str,
    year: str,
    *,
    plate: str = "",
    part_hint: str = "",
    existing_names: set[str] | None = None,
    network_links_fn=None,
) -> list[dict]:
    """Lista amplia de tipos de repuesto para cualquier vehículo."""
    brand = (brand or "").strip()
    model = (model or "").strip()
    year = (year or "").strip()
    plate = (plate or "").upper().strip()
    veh = " ".join(x for x in [brand, model, year] if x).strip()
    if not veh and plate:
        veh = f"placa {plate}"
    if not veh and not part_hint:
        return []

    hint = _norm(part_hint)
    taken = {_norm(x) for x in (existing_names or set())}
    out: list[dict] = []

    for category, name in _load_component_systems():
        nkey = _norm(name)
        if nkey in taken:
            continue
        if hint and hint not in nkey and hint not in _norm(category):
            if not any(term in nkey for term in hint.split() if len(term) > 2):
                continue
        q_oem = f"{name} {veh} OEM código fábrica".strip()
        links = [
            {
                "label": "Google OEM",
                "url": f"https://www.google.com/search?q={quote_plus(q_oem)}",
            },
            {
                "label": "Google repuesto",
                "url": f"https://www.google.com/search?q={quote_plus(f'{name} {veh} repuesto Costa Rica')}",
            },
        ]
        if network_links_fn:
            links = network_links_fn("", name, brand, model, year) or links

        out.append(
            {
                "category": category,
                "name": name,
                "oem_code": "Consultar OEM (VIN/motor)",
                "source": "catalogo_universal",
                "part_info": f"Componente del sistema {category}",
                "network_links": links[:6],
            }
        )
    return out


def overlay_factory_oem(parts: list[dict], profile: dict | None) -> list[dict]:
    """Pone código OEM de fábrica en filas universales cuando coincide el catálogo CR."""
    if not profile:
        return parts
    catalog: dict[str, dict] = {}
    for row in profile.get("parts") or []:
        key = _norm(row.get("name") or "")
        if key:
            catalog[key] = row
    for p in parts:
        src = p.get("source") or ""
        if src not in ("catalogo_universal", "catalogo_referencia"):
            continue
        n = _norm(p.get("name") or "")
        if not n:
            continue
        matched = catalog.get(n)
        if not matched:
            for ck, crow in catalog.items():
                if ck in n or n in ck:
                    matched = crow
                    break
        if not matched:
            continue
        code = (matched.get("oem_code") or "").strip()
        if code and "consultar" not in code.lower():
            p["oem_code"] = code
            p["source"] = "catalogo_referencia"
            p["part_info"] = "Código OEM original de fábrica (referencia Costa Rica)"
    return parts


def merge_oem_lists(primary: list[dict], extra: list[dict]) -> list[dict]:
    seen: set[str] = set()
    merged: list[dict] = []
    for row in primary + extra:
        key = _norm(row.get("name") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(row)
    return merged
