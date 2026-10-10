"""Amplía catálogo OEM Costa Rica: flota CR + plantillas OEM por marca."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

CATALOG_DIR = Path(__file__).resolve().parent / "catalog"
FLEET_PATH = CATALOG_DIR / "cr_vehicle_fleet.json"
TEMPLATES_PATH = CATALOG_DIR / "cr_brand_oem_templates.json"
COMPONENTS_PATH = CATALOG_DIR / "vehicle_components.json"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


@lru_cache(maxsize=1)
def _component_index() -> list[tuple[str, str]]:
    if not COMPONENTS_PATH.is_file():
        return []
    data = json.loads(COMPONENTS_PATH.read_text(encoding="utf-8"))
    rows: list[tuple[str, str]] = []
    for block in data.get("systems") or []:
        sys_name = (block.get("name") or "General").strip()
        for comp in block.get("components") or []:
            name = (comp or "").strip()
            if name:
                rows.append((sys_name, name))
    return rows


@lru_cache(maxsize=1)
def _brand_templates() -> dict[str, dict[str, str]]:
    if not TEMPLATES_PATH.is_file():
        return {}
    raw = json.loads(TEMPLATES_PATH.read_text(encoding="utf-8"))
    out: dict[str, dict[str, str]] = {}
    for brand, mapping in (raw.get("brands") or {}).items():
        out[_norm(brand)] = {_norm(k): str(v).strip() for k, v in (mapping or {}).items() if v}
    return out


@lru_cache(maxsize=1)
def _fleet_lines() -> list[dict]:
    if not FLEET_PATH.is_file():
        return []
    return list(json.loads(FLEET_PATH.read_text(encoding="utf-8")).get("lines") or [])


def _template_oem(brand_key: str, component_name: str) -> str:
    mapping = _brand_templates().get(brand_key) or {}
    key = _norm(component_name)
    if key in mapping:
        return mapping[key]
    for mk, code in mapping.items():
        if mk in key or key in mk:
            return code
    return ""


def parts_from_brand_template(brand: str) -> list[dict]:
    brand_key = _norm(brand)
    parts: list[dict] = []
    for category, name in _component_index():
        code = _template_oem(brand_key, name)
        if not code or "consultar" in code.lower():
            continue
        parts.append(
            {
                "category": category,
                "name": name,
                "oem_code": code,
            }
        )
    return parts


def _profile_key(prof: dict) -> tuple:
    b = _norm(prof.get("brand") or "")
    models = tuple(sorted(_norm(m) for m in prof.get("models") or []))
    return b, models


def _overlaps(existing: dict, new: dict) -> bool:
    if _norm(existing.get("brand") or "") != _norm(new.get("brand") or ""):
        return False
    em = {_norm(x) for x in existing.get("models") or []}
    nm = {_norm(x) for x in new.get("models") or []}
    if not (em & nm):
        return False
    y1 = int(existing.get("year_min") or 0)
    y2 = int(existing.get("year_max") or 9999)
    y3 = int(new.get("year_min") or 0)
    y4 = int(new.get("year_max") or 9999)
    return not (y2 < y3 or y4 < y1)


def merged_profiles(manual_profiles: list[dict]) -> list[dict]:
    """Manual + generados por flota CR (sin duplicar marca/modelo/año)."""
    out = [dict(p) for p in manual_profiles]
    seen_keys = {_profile_key(p) for p in out}
    for line in _fleet_lines():
        brand = (line.get("brand") or "").strip()
        if not brand:
            continue
        template_parts = parts_from_brand_template(brand)
        if not template_parts:
            continue
        prof = {
            "brand": brand,
            "models": list(line.get("models") or []),
            "year_min": int(line.get("year_min") or 2008),
            "year_max": int(line.get("year_max") or 2026),
            "regions": line.get("regions") or ["san_jose", "alajuela", "nacional"],
            "specs": {
                "zona_cr": "Flota Costa Rica",
                "catalogo": "Plantilla OEM marca + componentes CR",
            },
            "parts": template_parts,
        }
        if any(_overlaps(p, prof) for p in out):
            continue
        pk = _profile_key(prof)
        if pk in seen_keys:
            continue
        seen_keys.add(pk)
        out.append(prof)
    return out


def enrich_manual_profile_parts(profiles: list[dict]) -> list[dict]:
    """Completa perfiles manuales con plantilla de marca donde falte OEM."""
    result = []
    for prof in profiles:
        brand = prof.get("brand") or ""
        extra = parts_from_brand_template(brand)
        if not extra:
            result.append(prof)
            continue
        have = {_norm(p.get("name") or "") for p in prof.get("parts") or []}
        merged_parts = list(prof.get("parts") or [])
        for row in extra:
            nk = _norm(row.get("name") or "")
            if nk and nk not in have:
                merged_parts.append(row)
                have.add(nk)
        p2 = dict(prof)
        p2["parts"] = merged_parts
        result.append(p2)
    return result
