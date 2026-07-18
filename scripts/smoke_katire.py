"""
Katire smoke test — corre antes de entregar al cliente.
Uso: python scripts/smoke_katire.py
Sale con código != 0 si algo crítico falla.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILS: list[str] = []
OKS: list[str] = []


def ok(msg: str) -> None:
    OKS.append(msg)
    print(f"  OK  {msg}")


def fail(msg: str) -> None:
    FAILS.append(msg)
    print(f" FAIL {msg}")


def main() -> int:
    print("Katire smoke test\n" + "=" * 40)

    # 1) Imports
    try:
        from app.main import app  # noqa: F401
        from app.database import Base, SessionLocal, engine, migrate_schema
        from app.seed import seed_if_empty
        from app.pro import owner_analytics, seed_services
        from app.fe_service import readiness, get_issuer
        from app.fe_signer import CR_POLICY_ID
        from app.part_shops import ensure_default_shops
        from app.models import User, Supplier, AllyJob, Reception

        ok("imports")
    except Exception as exc:
        fail(f"imports: {exc}")
        traceback.print_exc()
        return 1

    # 2) Boot DB
    try:
        Base.metadata.create_all(bind=engine)
        migrate_schema()
        db = SessionLocal()
        try:
            seed_if_empty(db)
            seed_services(db)
            ensure_default_shops(db)
            assert db.query(User).filter(User.username == "admin").first()
            ok("boot + seed admin")
        finally:
            db.close()
    except Exception as exc:
        fail(f"boot: {exc}")
        traceback.print_exc()

    # 3) Dashboard (el fallo que tumbó Patio)
    try:
        db = SessionLocal()
        try:
            dash = owner_analytics(db)
            assert "board" in dash or "in_shop" in dash
            ok(f"dashboard in_shop={dash.get('in_shop')}")
        finally:
            db.close()
    except Exception as exc:
        fail(f"dashboard: {exc}")
        traceback.print_exc()

    # 4) FE readiness + signer policy
    try:
        db = SessionLocal()
        try:
            r = readiness(db)
            assert "checks" in r and "ready" in r
            assert "hacienda.go.cr" in CR_POLICY_ID
            ok(f"fe readiness ready={r['ready']} missing={r.get('missing')}")
        finally:
            db.close()
    except Exception as exc:
        fail(f"fe: {exc}")
        traceback.print_exc()

    # 5) HTTP API via TestClient
    try:
        from fastapi.testclient import TestClient
        from app.main import app
        from app.config import ADMIN_USERNAME, ADMIN_PASSWORD

        client = TestClient(app)
        h = client.get("/api/health")
        assert h.status_code == 200 and h.json().get("ok") is True
        ok(f"health build={h.json().get('build')}")

        login = client.post(
            "/api/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        )
        if login.status_code != 200:
            fail(f"login admin: {login.status_code} {login.text}")
        else:
            token = login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            ok("login admin")

            for path in [
                "/api/dashboard",
                "/api/receptions",
                "/api/parts",
                "/api/suppliers",
                "/api/ally-jobs",
                "/api/fe/readiness",
                "/api/fe/issuer",
                "/api/fe/invoices",
                "/api/fe/meta",
                "/api/settings",
                "/api/services",
                "/api/users",
                "/api/purchase-orders",
                "/api/appointments",
                "/api/parts/market-search?q=frenos",
            ]:
                res = client.get(path, headers=headers)
                if res.status_code != 200:
                    fail(f"GET {path} -> {res.status_code} {res.text[:180]}")
                else:
                    ok(f"GET {path}")

            # Flujo ingreso -> diagnóstico -> OT
            body = {
                "customer": {"name": "Smoke Cliente", "phone": "88888888"},
                "plate": "SMK-001",
                "brand": "Toyota",
                "model": "Yaris",
                "year": 2018,
                "customer_complaint": "Prueba smoke frenos",
                "customer_signature_name": "Smoke",
                "customer_accepted": True,
                "damages": [{"zone": "Frenos", "severity": "leve", "description": "ruido"}],
            }
            cr = client.post("/api/receptions", json=body, headers=headers)
            if cr.status_code != 200:
                fail(f"create reception: {cr.status_code} {cr.text[:220]}")
            else:
                rid = cr.json()["id"]
                ok(f"reception {cr.json().get('code')}")
                dg = client.post(
                    f"/api/receptions/{rid}/diagnosis",
                    json={
                        "technician": "Smoke",
                        "symptoms": "ruido",
                        "findings": "pastillas",
                        "recommended_work": "Cambio pastillas",
                        "estimated_hours": 1.5,
                        "priority": "normal",
                        "create_work_order": True,
                    },
                    headers=headers,
                )
                if dg.status_code != 200:
                    fail(f"diagnosis: {dg.status_code} {dg.text[:220]}")
                else:
                    wo = dg.json().get("work_order") or {}
                    ok(f"diagnosis+OT {wo.get('code')}")
                    pr = client.get(
                        f"/api/receptions/{rid}/diagnosis/print",
                        headers=headers,
                    )
                    if pr.status_code != 200 or "<html" not in pr.text.lower():
                        fail(f"print diagnosis: {pr.status_code}")
                    else:
                        ok("print diagnosis HTML")
                    if wo.get("id"):
                        wog = client.get(f"/api/work-orders/{wo['id']}", headers=headers)
                        if wog.status_code != 200:
                            fail(f"GET work-order: {wog.status_code}")
                        else:
                            ok(f"GET work-order {wo.get('code')}")
                        fe = client.post(
                            "/api/fe/issue",
                            json={
                                "work_order_id": wo["id"],
                                "tipo_documento": "04",
                                "send_now": False,
                            },
                            headers=headers,
                        )
                        if fe.status_code != 200:
                            fail(f"fe issue: {fe.status_code} {fe.text[:220]}")
                        else:
                            inv = fe.json()
                            clave = inv.get("clave") or ""
                            ok(f"fe xml clave_len={len(clave)}")
                            if len(clave) != 50:
                                fail(f"clave debe ser 50, es {len(clave)}")

            # shops seeded
            shops = client.get("/api/suppliers?kind=tienda", headers=headers).json()
            names = " ".join(s.get("name", "") for s in shops).lower()
            if "gigante" in names and ("guaca" in names or "guacamaya" in names):
                ok("tiendas Gigante/Guacamaya")
            else:
                fail(f"faltan tiendas base: {[s.get('name') for s in shops]}")

    except Exception as exc:
        fail(f"http: {exc}")
        traceback.print_exc()

    # 6) Static assets exist
    for rel in [
        "web/index.html",
        "web/login.html",
        "web/static/js/app.js",
        "web/static/js/ficha.js",
        "web/static/css/app.css",
        "app/fe_signer.py",
    ]:
        if (ROOT / rel).exists():
            ok(f"file {rel}")
        else:
            fail(f"missing {rel}")

    print("\n" + "=" * 40)
    print(f"Passed: {len(OKS)}  Failed: {len(FAILS)}")
    if FAILS:
        print("Fallos:")
        for f in FAILS:
            print(" -", f)
        return 1
    print("SMOKE OK — listo para cliente")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
