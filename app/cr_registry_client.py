"""Consulta vehículo Costa Rica por placa (Registro Nacional vía API comercial).

Solo expone datos del vehículo al taller. Propietarios, gravámenes e identificación
no se devuelven ni se persisten desde este módulo.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app.config import RNP_API_BASE, RNP_API_KEY, RNP_PLATE_CLASS

_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_TTL_SEC = 86_400

# Placas de prueba egobytes — funcionan sin RNP_API_KEY (demostración en taller).
_DEMO_VEHICLES: dict[str, dict[str, Any]] = {
    "DEMO001": {
        "brand": "TOYOTA",
        "model_full": "COROLLA XLI",
        "year": "2015",
        "color": "Gris",
        "vin": "JTDBT923000DEMO001",
        "fuel": "GASOLINA",
        "engine_displacement": "1800 C.C",
    },
    "DEMO002": {
        "brand": "NISSAN",
        "model_full": "SENTRA EX",
        "year": "2017",
        "color": "Blanco",
        "vin": "3N1AB7AP0HYDEMO002",
        "fuel": "GASOLINA",
        "engine_displacement": "1600 C.C",
    },
    "DEMO003": {
        "brand": "TOYOTA",
        "model_full": "COROLLA XLI",
        "year": "2018",
        "color": "Blanco",
        "vin": "JTDBT923000DEMO003",
        "fuel": "GASOLINA",
        "engine_displacement": "1800 C.C",
    },
    "DEMO004": {
        "brand": "HONDA",
        "model_full": "CB190R",
        "year": "2020",
        "color": "Rojo",
        "vin": "9C2MDEMO004000001",
        "fuel": "GASOLINA",
        "engine_displacement": "190 C.C",
    },
}


def registry_configured() -> bool:
    return bool(RNP_API_KEY)


def plate_lookup_enabled() -> bool:
    """Hay lookup por placa (demo local o Registro con clave)."""
    return registry_configured() or bool(_DEMO_VEHICLES)


def _demo_lookup(plate: str) -> dict[str, Any] | None:
    key = _norm_plate(plate)
    row = _DEMO_VEHICLES.get(key)
    if not row:
        return None
    return {
        "ok": True,
        "found": True,
        "brand": row["brand"],
        "model": _title_model(row["model_full"]),
        "model_full": row["model_full"],
        "year": str(row["year"]),
        "color": row.get("color") or "",
        "vin": (row.get("vin") or "").upper(),
        "fuel": row.get("fuel") or "",
        "engine_displacement": row.get("engine_displacement") or "",
        "engine_number": "",
        "provider": "demo_registro_cr",
        "owner_stored": False,
        "demo": True,
    }


def registry_status() -> dict:
    if not registry_configured():
        return {
            "configured": False,
            "connected": True,
            "demo_mode": True,
            "demo_plates": sorted(_DEMO_VEHICLES.keys()),
            "provider": "demo_registro_cr",
            "message": (
                "Modo demo: use placas DEMO001–DEMO004 para ver OEM por placa. "
                "Para placas reales agregue RNP_API_KEY (Registro Nacional CR API — egobytes)."
            ),
        }
    probe = lookup_vehicle_by_plate("DEMO003", use_cache=False)
    if probe.get("ok"):
        return {
            "configured": True,
            "connected": True,
            "provider": "registro_nacional_cr_api",
            "message": "Consulta por placa activa (solo datos del vehículo, sin propietario).",
        }
    return {
        "configured": True,
        "connected": False,
        "provider": "registro_nacional_cr_api",
        "message": probe.get("message") or "Clave presente pero la consulta falló — revise saldo o API key.",
    }


def _norm_plate(plate: str) -> str:
    return re.sub(r"[\s\-]", "", (plate or "").upper().strip())


def _split_plate_for_api(plate: str) -> tuple[str, str]:
    raw = _norm_plate(plate)
    clase = (RNP_PLATE_CLASS or "").upper().strip()
    m = re.match(r"^(CL|MOT)(.+)$", raw)
    if m:
        return m.group(2), m.group(1)
    if clase:
        return raw, clase
    return raw, ""


def _parse_year(value: Any) -> str:
    s = str(value or "").strip()
    m = re.search(r"(19|20)\d{2}", s)
    return m.group(0) if m else s


def _title_model(estilo: str) -> str:
    s = re.sub(r"\s+", " ", (estilo or "").strip())
    if not s:
        return ""
    first = s.split()[0]
    return first[:1].upper() + first[1:].lower() if first.isalpha() else s.title()


def _vehicle_only_payload(data: dict) -> dict[str, Any]:
    datos = data.get("datos") or data.get("data") or data
    veh = datos.get("vehiculo") or datos.get("vehicle") or {}
    motor = datos.get("motor") or datos.get("engine") or {}
    marca = (veh.get("marca") or veh.get("brand") or "").strip()
    estilo = (veh.get("estilo") or veh.get("model") or veh.get("style") or "").strip()
    vin = (
        veh.get("vin")
        or veh.get("numero_vin")
        or veh.get("no_vin")
        or veh.get("chasis")
        or ""
    ).strip()
    return {
        "ok": True,
        "found": True,
        "brand": marca,
        "model": _title_model(estilo),
        "model_full": estilo,
        "year": _parse_year(veh.get("ano_fabricacion") or veh.get("anio") or veh.get("year")),
        "color": (veh.get("color") or "").strip(),
        "vin": vin.upper() if vin else "",
        "body": (veh.get("carroceria") or veh.get("tipo_carroceria") or "").strip(),
        "fuel": (motor.get("combustible") or motor.get("fuel") or "").strip(),
        "engine_displacement": (motor.get("cilindrada") or motor.get("displacement") or "").strip(),
        "engine_number": (motor.get("numero") or motor.get("numero_motor") or "").strip(),
        "provider": "registro_nacional_cr_api",
        "owner_stored": False,
    }


def lookup_vehicle_by_plate(plate: str, *, use_cache: bool = True) -> dict[str, Any]:
    empty: dict[str, Any] = {
        "ok": False,
        "found": False,
        "brand": "",
        "model": "",
        "model_full": "",
        "year": "",
        "color": "",
        "vin": "",
        "provider": "registro_nacional_cr_api",
        "message": "",
    }
    demo = _demo_lookup(plate)
    if demo:
        cache_key = f"demo:{_norm_plate(plate)}"
        _CACHE[cache_key] = (time.time(), demo)
        return demo

    if not registry_configured():
        empty["message"] = (
            "Placa no demo. Configure RNP_API_KEY en Render o use DEMO001–DEMO004 para probar."
        )
        return empty

    segment, clase = _split_plate_for_api(plate)
    if len(segment) < 3:
        empty["message"] = "Placa muy corta"
        return empty

    cache_key = f"{clase}:{segment}"
    if use_cache:
        hit = _CACHE.get(cache_key)
        if hit and (time.time() - hit[0]) < _CACHE_TTL_SEC:
            return dict(hit[1])

    qs = f"?clase={urllib.parse.quote(clase)}" if clase else ""
    url = f"{RNP_API_BASE.rstrip('/')}/api/v1/vehiculos/placa/{urllib.parse.quote(segment)}{qs}"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "X-API-Key": RNP_API_KEY},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
            detail = body.get("error") or body.get("detail") or body.get("message") or ""
        except (json.JSONDecodeError, ValueError, AttributeError):
            detail = exc.reason or ""
        if exc.code == 404:
            out = {**empty, "message": "Placa no encontrada en el Registro"}
            _CACHE[cache_key] = (time.time(), out)
            return out
        out = {**empty, "message": detail or f"Registro respondió HTTP {exc.code}"}
        return out
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        out = {**empty, "message": str(exc) or "Sin respuesta del servicio de placa"}
        return out

    out = _vehicle_only_payload(raw)
    if not (out.get("brand") or out.get("model")):
        out = {**empty, "message": "Sin datos de vehículo para esta placa"}
        _CACHE[cache_key] = (time.time(), out)
        return out

    _CACHE[cache_key] = (time.time(), out)
    return out
