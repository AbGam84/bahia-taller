"""TecDoc Pegasus 3.0 (TecAlliance) — requiere licencia y claves del proveedor."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app.config import (
    TECDOC_API_KEY,
    TECDOC_ARTICLE_COUNTRY,
    TECDOC_BASE_URL,
    TECDOC_LANG,
    TECDOC_PROVIDER_ID,
)


def tecdoc_configured() -> bool:
    return bool(TECDOC_API_KEY and TECDOC_PROVIDER_ID)


def tecdoc_status() -> dict:
    if not tecdoc_configured():
        return {
            "configured": False,
            "message": "Agregue TECDOC_API_KEY y TECDOC_PROVIDER_ID en el servidor (licencia TecAlliance).",
        }
    ver = pegasus_call({"getVersion": {"provider": int(TECDOC_PROVIDER_ID)}})
    if ver is None:
        return {
            "configured": True,
            "connected": False,
            "message": "Claves presentes pero TecDoc no respondió — revise IP whitelist o API key.",
        }
    return {
        "configured": True,
        "connected": True,
        "message": "TecDoc Pegasus conectado.",
        "version": ver,
    }


def pegasus_call(body: dict) -> dict | None:
    if not tecdoc_configured():
        return None
    url = (
        f"{TECDOC_BASE_URL.rstrip('/')}/pegasus-3-0/services/TecdocToCatDLB.jsonEndpoint"
        f"?api_key={urllib.parse.quote(TECDOC_API_KEY)}"
    )
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None


def _articles_from_response(raw: dict | None) -> list[dict]:
    if not raw:
        return []
    articles = raw.get("articles") or raw.get("data", {}).get("articles") or []
    if isinstance(articles, dict):
        articles = articles.get("array") or articles.get("article") or []
    if not isinstance(articles, list):
        return []
    out: list[dict] = []
    for a in articles[:40]:
        if not isinstance(a, dict):
            continue
        nums = a.get("articleNumber") or a.get("articleNo") or ""
        oem = a.get("oemNumbers") or a.get("oemNo") or []
        oem_code = ""
        if isinstance(oem, list) and oem:
            first = oem[0]
            oem_code = first.get("articleNumber") if isinstance(first, dict) else str(first)
        elif isinstance(oem, str):
            oem_code = oem
        name = (
            a.get("genericArticleDescription")
            or a.get("articleName")
            or a.get("description")
            or nums
            or "Artículo TecDoc"
        )
        out.append(
            {
                "category": "TecDoc",
                "name": str(name).strip(),
                "oem_code": (oem_code or nums or "—").strip(),
                "source": "tecdoc",
                "tecdoc_article": nums,
                "brand": a.get("mfrName") or a.get("brandName") or "",
            }
        )
    return out


def search_articles(query: str, *, linkage_target_id: int | None = None) -> list[dict]:
    """Busca artículos IAM/OEM en TecDoc por texto o número."""
    q = (query or "").strip()
    if not q or not tecdoc_configured():
        return []
    payload: dict[str, Any] = {
        "getArticles": {
            "provider": int(TECDOC_PROVIDER_ID),
            "articleCountry": TECDOC_ARTICLE_COUNTRY,
            "lang": TECDOC_LANG,
            "searchType": 0,
            "searchQuery": q,
            "perPage": 30,
            "page": 1,
            "includeAll": True,
        }
    }
    if linkage_target_id:
        payload["getArticles"]["linkageTargetId"] = linkage_target_id
    raw = pegasus_call(payload)
    return _articles_from_response(raw)


def vehicles_by_vin(vin: str) -> list[dict]:
    vin = (vin or "").strip().upper()
    if len(vin) < 11 or not tecdoc_configured():
        return []
    raw = pegasus_call(
        {
            "getVehiclesByVIN": {
                "provider": int(TECDOC_PROVIDER_ID),
                "country": TECDOC_ARTICLE_COUNTRY,
                "vin": vin,
                "lang": TECDOC_LANG,
            }
        }
    )
    if not raw:
        return []
    cars = raw.get("data") or raw.get("vehicles") or raw.get("array") or []
    if isinstance(cars, dict):
        cars = cars.get("array") or [cars]
    return [c for c in cars if isinstance(c, dict)]


def enrich_parts(
    *,
    brand: str,
    model: str,
    year: int,
    vin: str = "",
    part_hint: str = "",
) -> tuple[list[dict], dict]:
    """Devuelve piezas TecDoc + meta de conexión."""
    meta = {"tecdoc": tecdoc_status()}
    if not tecdoc_configured():
        return [], meta

    parts: list[dict] = []
    linkage_id = None
    if vin:
        for car in vehicles_by_vin(vin):
            linkage_id = car.get("linkageTargetId") or car.get("carId") or car.get("vehicleId")
            if linkage_id:
                meta["tecdoc_vehicle"] = {
                    "description": car.get("vehicleDescription") or car.get("description") or "",
                    "linkageTargetId": linkage_id,
                }
                break

    queries: list[str] = []
    if part_hint:
        queries.append(f"{part_hint} {brand} {model}".strip())
        queries.append(part_hint)
    if brand or model:
        queries.append(f"{brand} {model} {year or ''} repuesto".strip())
        queries.append(f"{brand} {model} {year or ''}".strip())
    if vin and not queries:
        queries.append(vin)
    seen: set[str] = set()
    for q in queries[:4]:
        for row in search_articles(q, linkage_target_id=int(linkage_id) if linkage_id else None):
            key = (row.get("oem_code"), row.get("name"))
            if key in seen:
                continue
            seen.add(key)
            parts.append(row)
    return parts[:35], meta
