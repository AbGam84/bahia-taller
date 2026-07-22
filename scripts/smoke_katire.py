"""
Katire — contrato del producto (camino feliz).

Esto NO es un chequeo parcial: es la definición de “funciona”.
Si falla, no se entrega al cliente.

Uso: python scripts/smoke_katire.py
"""

from __future__ import annotations

import io
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILS: list[str] = []
OKS: list[str] = []
WARNS: list[str] = []


def ok(msg: str) -> None:
    OKS.append(msg)
    print(f"  OK  {msg}")


def warn(msg: str) -> None:
    WARNS.append(msg)
    print(f" WARN {msg}")


def fail(msg: str) -> None:
    FAILS.append(msg)
    print(f" FAIL {msg}")


def expect(res, code: int, label: str) -> dict | list | None:
    if res.status_code != code:
        fail(f"{label}: {res.status_code} {res.text[:240]}")
        return None
    ok(label)
    try:
        return res.json()
    except Exception:
        return None


def main() -> int:
    print("Katire product contract (camino feliz)\n" + "=" * 48)

    try:
        from app.main import app  # noqa: F401
        from app.database import Base, SessionLocal, engine, migrate_schema
        from app.seed import seed_if_empty
        from app.pro import owner_analytics
        from app.fe_service import readiness
        from app.fe_signer import CR_POLICY_ID
        from app.models import Part, ServiceCatalog, User

        ok("imports")
    except Exception as exc:
        fail(f"imports: {exc}")
        traceback.print_exc()
        return 1

    try:
        Base.metadata.create_all(bind=engine)
        migrate_schema()
        db = SessionLocal()
        try:
            seed_if_empty(db)
            assert db.query(User).filter(User.username == "admin").first()
            parts_n = db.query(Part).count()
            svc_n = db.query(ServiceCatalog).count()
            assert parts_n >= 5, f"parts={parts_n}"
            assert svc_n >= 4, f"services={svc_n}"
            ok(f"boot + seed catalog parts={parts_n} services={svc_n}")
        finally:
            db.close()
    except Exception as exc:
        fail(f"boot: {exc}")
        traceback.print_exc()

    try:
        db = SessionLocal()
        try:
            dash = owner_analytics(db)
            assert "board" in dash or "in_shop" in dash
            ok(f"dashboard in_shop={dash.get('in_shop')}")
            r = readiness(db)
            assert "checks" in r and "ready" in r
            assert "hacienda.go.cr" in CR_POLICY_ID
            ok(f"fe readiness ready={r['ready']}")
        finally:
            db.close()
    except Exception as exc:
        fail(f"dashboard/fe: {exc}")
        traceback.print_exc()

    try:
        from fastapi.testclient import TestClient
        from app.main import app
        from app.config import ADMIN_USERNAME, ADMIN_PASSWORD, DEMO_USERNAME, DEMO_PASSWORD

        client = TestClient(app)

        h = client.get("/api/health")
        data = h.json()
        if h.status_code != 200 or not data.get("ok") or not data.get("db"):
            fail(f"health unhealthy: {h.status_code} {data}")
        else:
            ok(f"health build={data.get('build')}")

        # --- Admin: lectura de módulos ---
        login = client.post("/api/auth/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        if login.status_code != 200:
            fail(f"login admin: {login.status_code} {login.text}")
            return 1
        admin_h = {"Authorization": f"Bearer {login.json()['access_token']}"}
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
            res = client.get(path, headers=admin_h)
            if res.status_code != 200:
                fail(f"GET {path} -> {res.status_code} {res.text[:160]}")
            else:
                ok(f"GET {path}")

        parts = client.get("/api/parts", headers=admin_h).json()
        if not isinstance(parts, list) or len(parts) < 5:
            fail(f"bodega vacía: {len(parts) if isinstance(parts, list) else parts}")
        else:
            ok(f"bodega con {len(parts)} piezas")

        # --- Demo recepcion: camino feliz completo ---
        dlogin = client.post("/api/auth/login", json={"username": DEMO_USERNAME, "password": DEMO_PASSWORD})
        if dlogin.status_code != 200:
            fail(f"login demo: {dlogin.status_code} {dlogin.text}")
            return 1
        demo_h = {"Authorization": f"Bearer {dlogin.json()['access_token']}"}
        ok(f"login demo role={dlogin.json()['user'].get('role')}")

        put_set = client.put(
            "/api/settings",
            headers=demo_h,
            json={
                "shop_name": "Autorespuesto",
                "slogan": "De la llave al XML.",
                "phone": "+506 8870-8123",
                "whatsapp": "+506 8870-8123",
                "address": "Costa Rica",
                "labor_rate": 15000,
                "sinpe_phone": "88708123",
                "sinpe_name": "Autorespuesto",
            },
        )
        expect(put_set, 200, "settings PUT recepcion")

        body = {
            "customer": {"name": "Contrato Cliente", "phone": "88880011"},
            "plate": "CTR-001",
            "brand": "Toyota",
            "model": "Yaris",
            "year": 2019,
            "customer_complaint": "Chillido al frenar",
            "customer_signature_name": "Contrato Cliente",
            "customer_accepted": True,
            "damages": [{"zone": "Frenos", "severity": "leve", "description": "ruido"}],
        }
        cr = client.post("/api/receptions", json=body, headers=demo_h)
        rec = expect(cr, 200, "ingreso recepción")
        if not rec:
            return 1
        rid = rec["id"]
        token_pub = rec.get("public_token") or ""

        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
            b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        photo = client.post(
            f"/api/receptions/{rid}/photos",
            headers=demo_h,
            files={"file": ("ingreso.png", io.BytesIO(png), "image/png")},
            data={"zone": "Ingreso", "caption": "Foto smoke"},
        )
        expect(photo, 200, "foto ingreso")

        insp = client.put(
            f"/api/receptions/{rid}/inspection",
            headers=demo_h,
            json={
                "items": [
                    {"system_key": "frenos", "status": "fail", "notes": "pastillas"},
                    {"system_key": "motor", "status": "fail", "notes": "fuga aceite"},
                ]
            },
        )
        expect(insp, 200, "inspección DVI (frenos+motor)")

        pr = client.get(f"/api/receptions/{rid}/diagnosis/print", headers=demo_h)
        if pr.status_code != 200:
            fail(f"print mapa: {pr.status_code} {pr.text[:200]}")
        else:
            html = pr.text or ""
            markers = ("Mapa del vehículo", "Autorización del cliente", "FALLA")
            if any(m in html for m in markers):
                ok("print mapa DVI con contenido")
            else:
                fail("print mapa sin Mapa/Autorización/FALLA")

        dg = client.post(
            f"/api/receptions/{rid}/diagnosis",
            headers=demo_h,
            json={
                "technician": "Mecánico demo",
                "symptoms": "chillido",
                "findings": "pastillas gastadas",
                "recommended_work": "Cambio pastillas delanteras",
                "estimated_hours": 1.5,
                "priority": "normal",
                "create_work_order": True,
            },
        )
        dg_data = expect(dg, 200, "diagnóstico + OT")
        wo = (dg_data or {}).get("work_order") or {}
        if not wo.get("id"):
            fail("diagnóstico sin OT")
        else:
            ok(f"OT {wo.get('code')}")

        st = client.patch(
            f"/api/receptions/{rid}/status",
            headers=demo_h,
            json={"status": "en_reparacion"},
        )
        st_data = expect(st, 200, "avance en_reparacion")
        if st_data and st_data.get("status") != "en_reparacion":
            fail(f"status quedó {st_data.get('status')}")

        if token_pub:
            pub = client.get(f"/api/public/{token_pub}")
            pub_data = expect(pub, 200, "portal cliente")
            if pub_data:
                tl = pub_data.get("timeline") or []
                repair_done = any(t.get("key") == "en_reparacion" and t.get("done") for t in tl)
                if not repair_done:
                    fail("timeline no avanzó a en_reparacion")
                else:
                    ok("timeline avance público")

        est = client.post(f"/api/receptions/{rid}/estimate", headers=demo_h, json={})
        est_data = expect(est, 200, "cotización")
        if est_data and not (est_data.get("estimate") or est_data.get("public_url")):
            fail("cotización sin estimate/public_url")

        part_id = parts[0]["id"]
        line = client.post(
            f"/api/work-orders/{wo['id']}/lines",
            headers=demo_h,
            json={"part_id": part_id, "quantity": 1, "description": "repuesto smoke"},
        )
        expect(line, 200, "usar repuesto en OT")

        allies = client.get("/api/suppliers?kind=aliado", headers=demo_h).json()
        if not allies:
            fail("sin aliados sembrados")
        else:
            ok(f"aliados={len(allies)}")
            aj = client.post(
                "/api/ally-jobs",
                headers=demo_h,
                json={
                    "ally_id": allies[0]["id"],
                    "reception_id": rid,
                    "work_order_id": wo.get("id"),
                    "plate": "CTR-001",
                    "vehicle_info": "Toyota Yaris 2019",
                    "job_type": "rectificacion",
                    "description": "Rectificación demo smoke",
                    "cost_estimated": 40000,
                },
            )
            job = expect(aj, 200, "crear trabajo aliado")
            if job and job.get("id"):
                patch = client.patch(
                    f"/api/ally-jobs/{job['id']}",
                    headers=demo_h,
                    json={"status": "enviado", "note": "salió del patio"},
                )
                expect(patch, 200, "seguimiento aliado")

        ready = client.patch(
            f"/api/receptions/{rid}/status",
            headers=demo_h,
            json={"status": "listo"},
        )
        expect(ready, 200, "avance listo")

        # Admin: FE + SINPE sobre la misma OT (FE opcional si falta cert Hacienda)
        if wo.get("id"):
            fe = client.post(
                "/api/fe/issue",
                headers=admin_h,
                json={"work_order_id": wo["id"], "tipo_documento": "04", "send_now": False},
            )
            if fe.status_code == 200:
                inv = fe.json()
                if len(inv.get("clave") or "") != 50:
                    fail(f"clave FE len={len(inv.get('clave') or '')}")
                else:
                    ok("emitir FE XML")
            else:
                detail = fe.text[:240].lower()
                cert_missing = any(
                    k in detail
                    for k in ("cert", "p12", "atv", "hacienda", "pin", "readiness", "no está listo")
                )
                if cert_missing:
                    warn(f"emitir FE XML omitido (sin cert): {fe.status_code}")
                else:
                    fail(f"emitir FE XML: {fe.status_code} {fe.text[:200]}")

            sinpe = client.post(
                "/api/payments/sinpe-link",
                headers=admin_h,
                json={"work_order_id": wo["id"]},
            )
            sp = expect(sinpe, 200, "SINPE cierre")
            if sp and (not sp.get("reference") or not sp.get("message")):
                fail("SINPE sin referencia/mensaje")

            paid = client.post(f"/api/work-orders/{wo['id']}/mark-paid", headers=admin_h)
            expect(paid, 200, "marcar pagado")

        shops = client.get("/api/suppliers?kind=tienda", headers=admin_h).json()
        names = " ".join(s.get("name", "") for s in shops).lower()
        if "gigante" in names and ("guaca" in names or "guacamaya" in names):
            ok("tiendas Gigante/Guacamaya")
        else:
            fail(f"faltan tiendas base: {[s.get('name') for s in shops]}")

    except Exception as exc:
        fail(f"http: {exc}")
        traceback.print_exc()

    for rel in [
        "web/index.html",
        "web/login.html",
        "web/static/js/app.js",
        "web/static/js/ficha.js",
        "web/static/js/taller-dvi.js",
        "web/static/css/app.css",
    ]:
        if (ROOT / rel).exists():
            ok(f"file {rel}")
        else:
            fail(f"missing {rel}")

    idx = (ROOT / "web/index.html").read_text(encoding="utf-8")
    if "taller-dvi.js?v=" in idx and "app.js?v=" in idx:
        ok("index.html carga app.js + taller-dvi.js")
    else:
        fail("index.html falta app.js / taller-dvi.js")
    app_pos = idx.find("app.js")
    dvi_pos = idx.find("taller-dvi.js")
    if app_pos >= 0 and dvi_pos > app_pos:
        ok("index.html app.js antes de taller-dvi.js")
    else:
        fail("index.html orden scripts incorrecto")

    print("\n" + "=" * 48)
    print(f"Passed: {len(OKS)}  Warned: {len(WARNS)}  Failed: {len(FAILS)}")
    if WARNS:
        print("Avisos:")
        for w in WARNS:
            print(" ~", w)
    if FAILS:
        print("Fallos:")
        for f in FAILS:
            print(" -", f)
        return 1
    print("CONTRATO OK — listo para cliente")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
