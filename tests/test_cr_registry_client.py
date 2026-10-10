"""Pruebas locales del cliente Registro CR (sin red)."""

import os

from app.cr_registry_client import (
    _split_plate_for_api,
    _title_model,
    _vehicle_only_payload,
    lookup_vehicle_by_plate,
)


def test_split_plate_cl_prefix():
    seg, clase = _split_plate_for_api("CL-123456")
    assert clase == "CL"
    assert seg == "123456"


def test_title_model_corolla():
    assert _title_model("COROLLA XLI") == "Corolla"


def test_vehicle_only_payload_strips_owner_block():
    raw = {
        "datos": {
            "vehiculo": {
                "marca": "TOYOTA",
                "estilo": "COROLLA XLI",
                "ano_fabricacion": "2018",
                "vin": "JTDB123456789",
            },
            "motor": {"cilindrada": "1800 C.C", "combustible": "GASOLINA"},
            "propietarios": [{"nombre": "NO DEBE SALIR", "numero_identificacion": "1"}],
        }
    }
    out = _vehicle_only_payload(raw)
    assert out["brand"] == "TOYOTA"
    assert out["model"] == "Corolla"
    assert out["year"] == "2018"
    assert "NO DEBE" not in str(out)


def test_demo_plate_without_api_key(monkeypatch):
    monkeypatch.delenv("RNP_API_KEY", raising=False)
    from app import config

    monkeypatch.setattr(config, "RNP_API_KEY", "")
    out = lookup_vehicle_by_plate("DEMO003", use_cache=False)
    assert out.get("ok") is True
    assert out.get("model") == "Corolla"
    assert out.get("demo") is True
