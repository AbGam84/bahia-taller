"""Documentos imprimibles Katire (diagnóstico / OT + mapa DVI)."""

from __future__ import annotations

from html import escape

from app.models import Reception

# Posiciones del mapa para impresión (vista superior simplificada)
_MAP_ZONES = [
    ("luces", "Luces", 70, 18, 60, 22),
    ("carroceria", "Carrocería", 45, 48, 110, 90),
    ("motor", "Motor", 60, 55, 80, 40),
    ("fluidos", "Fluidos", 78, 70, 44, 18),
    ("aire", "A/C", 70, 100, 60, 28),
    ("direccion", "Dirección", 55, 145, 40, 36),
    ("electrico", "Eléctrico", 105, 145, 40, 36),
    ("transmision", "Transmisión", 70, 188, 60, 30),
    ("suspension", "Suspensión", 40, 188, 24, 55),
    ("suspension_r", "Suspensión", 136, 188, 24, 55),
    ("frenos", "Frenos", 38, 250, 28, 28),
    ("frenos_r", "Frenos", 134, 250, 28, 28),
    ("escape", "Escape", 85, 250, 30, 40),
    ("llantas", "Llantas", 36, 282, 32, 22),
    ("llantas_r", "Llantas", 132, 282, 32, 22),
]

_FILL = {
    "ok": "#7dcea0",
    "watch": "#f0c35a",
    "fail": "#ff6b7a",
    "na": "#d5dde3",
}


def _zone_key(raw: str) -> str:
    return raw.replace("_r", "")


def _car_map_svg(checks: list) -> str:
    by = {_zone_key(c.system_key): c.status for c in checks}
    parts = []
    for key, label, x, y, w, h in _MAP_ZONES:
        st = by.get(_zone_key(key), "na")
        fill = _FILL.get(st, _FILL["na"])
        parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" '
            f'fill="{fill}" stroke="#334155" stroke-width="1.2"/>'
            f'<text x="{x + w / 2}" y="{y + h / 2 + 3}" text-anchor="middle" '
            f'font-size="7" font-family="Manrope,sans-serif" fill="#0e1620">{escape(label)}</text>'
        )
    return (
        '<svg viewBox="0 0 200 320" width="180" height="288" xmlns="http://www.w3.org/2000/svg" '
        'style="border:1px solid #d7e0e6;border-radius:12px;background:#f4f7f9">'
        + "".join(parts)
        + "</svg>"
    )


def diagnosis_print_html(r: Reception, shop_name: str = "Aitorepuestos") -> str:
    v = r.vehicle
    c = v.customer if v else None
    d = r.diagnosis
    wo = r.work_order
    checks = sorted(r.inspection_checks or [], key=lambda x: x.sort_order)
    status_label = {
        "ok": "OK",
        "watch": "Vigilar",
        "fail": "FALLA",
        "na": "Sin revisar",
    }

    fails = [ch for ch in checks if ch.status in ("fail", "watch")]
    fail_rows = "".join(
        f"<tr><td>{escape(ch.system_name)}</td>"
        f"<td><strong>{escape(status_label.get(ch.status, ch.status))}</strong></td>"
        f"<td>{escape(ch.notes or '')}</td></tr>"
        for ch in fails
    ) or "<tr><td colspan='3'>Sin fallas marcadas en el mapa</td></tr>"

    dvi_rows = "".join(
        f"<tr><td>{escape(ch.system_name)}</td><td>{escape(status_label.get(ch.status, ch.status))}</td>"
        f"<td>{escape(ch.notes or '')}</td></tr>"
        for ch in checks
    ) or "<tr><td colspan='3'>Sin lectura de sistemas</td></tr>"

    damages = "".join(
        f"<li><strong>{escape(x.zone)}</strong> ({escape(x.severity)}): {escape(x.description or '')}</li>"
        for x in (r.damages or [])
    ) or "<li>Ninguno registrado</li>"

    wo_block = ""
    if wo:
        lines = "".join(
            f"<li>{escape(l.description)} × {l.quantity} — ₡{l.line_total:,.0f}</li>" for l in (wo.lines or [])
        ) or "<li>Sin líneas de repuesto</li>"
        wo_block = f"""
        <div class="box">
          <h2>Orden de trabajo {escape(wo.code)}</h2>
          <p>Estado: {escape(wo.status)} · Técnico: {escape(wo.assigned_to or '')}</p>
          <p>Mano de obra: ₡{wo.labor_total:,.0f} · Repuestos: ₡{wo.parts_total:,.0f}
             · <strong>Total ₡{wo.grand_total:,.0f}</strong></p>
          <p>{escape(wo.labor_notes or '')}</p>
          <ul>{lines}</ul>
        </div>"""

    diag_block = ""
    if d:
        diag_block = f"""
        <div class="box">
          <h2>Diagnóstico del mecánico</h2>
          <p><strong>Técnico:</strong> {escape(d.technician or '')} ·
             <strong>Prioridad:</strong> {escape(d.priority or '')} ·
             <strong>Horas:</strong> {d.estimated_hours or 0}</p>
          <p><strong>Síntomas:</strong><br/>{escape(d.symptoms or '').replace(chr(10), '<br/>')}</p>
          <p><strong>Hallazgos:</strong><br/>{escape(d.findings or '').replace(chr(10), '<br/>')}</p>
          <p><strong>OBD:</strong> {escape(d.obd_codes or '—')}</p>
          <p><strong>Trabajo recomendado:</strong><br/>{escape(d.recommended_work or '').replace(chr(10), '<br/>')}</p>
        </div>"""
    else:
        diag_block = "<div class='box'><p>Mapa de fallas listo. Complete el diagnóstico en pantalla si aún no está.</p></div>"

    plate = escape(v.plate if v else "")
    brand = escape(v.brand if v else "")
    model = escape(v.model if v else "")
    year = v.year if v else ""
    cname = escape(c.name if c else "")
    cphone = escape(c.phone if c else "")
    car_svg = _car_map_svg(checks)

    return f"""<!doctype html>
<html lang="es"><head>
<meta charset="utf-8"/>
<title>Diagnóstico {escape(r.code)} · Aitorepuestos</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@700&family=Manrope:wght@400;600;700&display=swap');
  body{{font-family:Manrope,sans-serif;color:#0e1620;margin:0;padding:28px;background:#f7f1ea}}
  h1{{font-family:Unbounded,sans-serif;font-size:24px;margin:0;letter-spacing:-0.03em}}
  h2{{font-family:Unbounded,sans-serif;font-size:14px;margin:0 0 8px}}
  .tag{{color:#5a6a74;margin:4px 0 18px}}
  .box{{background:#fff;border:1px solid #d7e0e6;border-radius:12px;padding:14px 16px;margin:12px 0}}
  .row{{display:flex;gap:18px;align-items:flex-start;flex-wrap:wrap}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  th,td{{border-bottom:1px solid #e4ebef;padding:7px 6px;text-align:left}}
  th{{color:#5a6a74;font-size:11px;text-transform:uppercase;letter-spacing:0.06em}}
  .legend{{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;margin-top:8px}}
  .dot{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px}}
  .foot{{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:28px;font-size:13px}}
  .line{{border-top:1px solid #9aa8b0;padding-top:8px;margin-top:40px;min-height:56px}}
  .auth{{border:2px dashed #94a3b8;border-radius:12px;padding:14px;margin-top:16px}}
  @media print{{body{{padding:10px;background:#fff}} .noprint{{display:none}}}}
</style>
</head><body>
  <div class="noprint" style="margin-bottom:14px;display:flex;gap:8px;flex-wrap:wrap">
    <button onclick="window.print()" style="padding:10px 14px;border-radius:10px;border:0;background:#ff4d2e;color:#fff;font-weight:700;cursor:pointer">Imprimir / PDF</button>
    <span style="align-self:center;color:#5a6a74;font-size:13px">Entregue al cliente, pida firma y luego asigne el carro al taller en Katire.</span>
  </div>
  <h1>Aitorepuestos · Diagnóstico digital</h1>
  <p class="tag">Katire · {escape(r.code)} · {escape(r.status)} · {escape((r.created_at.isoformat() if r.created_at else '')[:16])}</p>
  <div class="box">
    <p><strong>Vehículo:</strong> {plate} · {brand} {model} {year}<br/>
    <strong>Cliente:</strong> {cname} · {cphone}<br/>
    <strong>Queja:</strong> {escape(r.customer_complaint or '')}<br/>
    <strong>Km / combustible:</strong> {r.odometer_km} · {escape(r.fuel_level or '')}</p>
  </div>
  <div class="box">
    <h2>Mapa del vehículo (fallas marcadas)</h2>
    <div class="row">
      <div>{car_svg}
        <div class="legend">
          <span><i class="dot" style="background:#7dcea0"></i>OK</span>
          <span><i class="dot" style="background:#f0c35a"></i>Vigilar</span>
          <span><i class="dot" style="background:#ff6b7a"></i>Falla</span>
          <span><i class="dot" style="background:#d5dde3"></i>Sin revisar</span>
        </div>
      </div>
      <div style="flex:1;min-width:220px">
        <h2>Fallas / puntos a vigilar</h2>
        <table><thead><tr><th>Parte</th><th>Estado</th><th>Nota</th></tr></thead>
        <tbody>{fail_rows}</tbody></table>
      </div>
    </div>
  </div>
  <div class="box">
    <h2>Daños al llegar</h2>
    <ul>{damages}</ul>
  </div>
  <div class="box">
    <h2>Lectura completa por sistemas</h2>
    <table><thead><tr><th>Sistema</th><th>Estado</th><th>Notas</th></tr></thead>
    <tbody>{dvi_rows}</tbody></table>
  </div>
  {diag_block}
  {wo_block}
  <div class="box auth">
    <h2>Autorización del cliente</h2>
    <p>Declaro que me explicaron el diagnóstico y autorizo a <strong>{escape(shop_name)}</strong>
       a asignar este vehículo al taller / generar la orden de trabajo según lo indicado.</p>
    <div class="foot">
      <div>
        <div class="line">Nombre completo<br/><strong>{cname}</strong></div>
      </div>
      <div>
        <div class="line">Firma del cliente<br/>&nbsp;</div>
      </div>
    </div>
    <div class="foot">
      <div><div class="line">Técnico<br/><strong>{escape((d.technician if d else '') or '')}</strong></div></div>
      <div><div class="line">Fecha / cédula<br/>&nbsp;</div></div>
    </div>
  </div>
  <p class="tag" style="margin-top:28px">De la llave al XML. · Katire · Aitorepuestos</p>
</body></html>"""
