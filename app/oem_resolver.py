"""Resuelve nombre y código OEM de fábrica por componente (marca/modelo/año)."""

from __future__ import annotations

import re


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", _norm(s)) if len(t) > 2}


def is_placeholder_oem(code: str) -> bool:
    c = (code or "").strip().lower()
    if not c or c == "—":
        return True
    return "consultar" in c or "vin" in c


def catalog_rows_for_vehicle(brand: str, model: str, year: int) -> list[dict]:
    from app.oem_network import _load_catalog, match_oem_profile, normalize_brand

    brand = normalize_brand(brand)
    profile = match_oem_profile(brand, model, year)
    rows: list[dict] = []
    seen: set[str] = set()
    if profile:
        for row in profile.get("parts") or []:
            key = _norm(row.get("name") or "")
            if key and key not in seen:
                seen.add(key)
                rows.append(dict(row))
    b = _norm(brand)
    m = _norm(model)
    for prof in _load_catalog().get("profiles") or []:
        if _norm(prof.get("brand") or "") != b:
            continue
        models = [_norm(x) for x in prof.get("models") or []]
        if m and not any(pm == m or pm in m or m in pm for pm in models):
            continue
        for row in prof.get("parts") or []:
            key = _norm(row.get("name") or "")
            if key and key not in seen:
                seen.add(key)
                rows.append(dict(row))
    return rows


def _score_row(component_name: str, category: str, row: dict) -> int:
    cn = _tokens(component_name)
    rn = _tokens(row.get("name") or "")
    cat = _norm(category or "")
    rc = _norm(row.get("category") or "")
    if not cn or not rn:
        return 0
    inter = len(cn & rn)
    if inter == 0:
        return 0
    score = inter * 3
    if cn == rn:
        score += 8
    if cat and rc and (cat in rc or rc in cat):
        score += 2
    # Sinónimos frecuentes
    pairs = [
        ({"disco", "embrague"}, {"disco", "embrague"}),
        ({"plato", "presion"}, {"plato", "presion", "embrague"}),
        ({"collarin", "bearing"}, {"collarin", "bearing", "embrague"}),
        ({"kit", "embrague"}, {"kit", "embrague", "embrague"}),
        ({"pastillas", "freno", "delanteras"}, {"pastillas", "freno", "delanteras"}),
        ({"pastillas", "freno", "traseras"}, {"pastillas", "freno", "traseras"}),
        ({"filtro", "aceite"}, {"filtro", "aceite"}),
        ({"filtro", "aire"}, {"filtro", "aire"}),
        ({"filtro", "cabina", "polen"}, {"filtro", "cabina"}),
        ({"bujias", "juego"}, {"bujia"}),
        ({"bobina", "encendido"}, {"bobina", "encendido"}),
        ({"bomba", "agua"}, {"bomba", "agua"}),
        ({"amortiguador", "delantero"}, {"amortiguador", "delantero"}),
        ({"amortiguador", "trasero"}, {"amortiguador", "trasero"}),
        ({"discos", "freno", "delanteros"}, {"discos", "freno", "delanteros"}),
    ]
    for a, b in pairs:
        if a <= cn and b <= rn:
            score += 5
    return score


def best_catalog_match(component_name: str, category: str, catalog: list[dict]) -> dict | None:
    best = None
    best_score = 0
    for row in catalog:
        sc = _score_row(component_name, category, row)
        code = (row.get("oem_code") or "").strip()
        if sc > best_score and code and not is_placeholder_oem(code):
            best_score = sc
            best = row
    return best if best_score >= 5 else None


def apply_real_oem_codes(parts: list[dict], brand: str, model: str, year: int) -> list[dict]:
    from app.cr_catalog_merge import parts_from_brand_template
    from app.oem_network import normalize_brand

    brand = normalize_brand(brand)
    if not brand:
        return parts
    if not (model or "").strip():
        template_rows = parts_from_brand_template(brand)
        catalog = template_rows
    else:
        catalog = catalog_rows_for_vehicle(brand, model, year)
    if not catalog:
        return parts
    for p in parts:
        if not is_placeholder_oem(p.get("oem_code") or ""):
            p["factory_name"] = (p.get("factory_name") or p.get("name") or "").strip()
            p["part_info"] = p.get("part_info") or "Código OEM original de fábrica"
            continue
        hit = best_catalog_match(p.get("name") or "", p.get("category") or "", catalog)
        if not hit:
            continue
        code = (hit.get("oem_code") or "").strip()
        official = (hit.get("name") or p.get("name") or "").strip()
        p["oem_code"] = code
        p["factory_name"] = official
        p["name"] = official
        p["source"] = "catalogo_referencia"
        p["part_info"] = "Nombre y código OEM original de fábrica (catálogo CR)"
    return parts


def fill_tecdoc_oem_gaps(
    parts: list[dict],
    brand: str,
    model: str,
    year: int,
    vin: str = "",
    *,
    max_lookups: int = 12,
) -> list[dict]:
    from app.tecdoc_client import search_articles, tecdoc_configured

    if not tecdoc_configured() or not brand:
        return parts
    pending = [p for p in parts if is_placeholder_oem(p.get("oem_code") or "")]
    if not pending:
        return parts
    linkage_id = None
    if vin:
        from app.tecdoc_client import vehicles_by_vin

        for car in vehicles_by_vin(vin):
            linkage_id = car.get("linkageTargetId") or car.get("carId")
            if linkage_id:
                break
    lookups = 0
    for p in pending:
        if lookups >= max_lookups:
            break
        q = f"{p.get('name')} {brand} {model} {year or ''}".strip()
        rows = search_articles(q, linkage_target_id=int(linkage_id) if linkage_id else None)
        lookups += 1
        if not rows:
            continue
        top = rows[0]
        code = (top.get("oem_code") or "").strip()
        if not code or is_placeholder_oem(code):
            continue
        p["oem_code"] = code
        p["factory_name"] = (top.get("name") or p.get("name") or "").strip()
        p["name"] = p["factory_name"]
        p["source"] = "tecdoc"
        p["part_info"] = "Artículo OEM vía TecDoc"
        if top.get("tecdoc_article"):
            p["tecdoc_article"] = top["tecdoc_article"]
    return parts
