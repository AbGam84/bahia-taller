"""Documentos imprimibles Katire (diagnóstico / OT)."""

from __future__ import annotations

from html import escape

from app.models import Reception


def diagnosis_print_html(r: Reception, shop_name: str = "Aitorepuestos") -> str:
    v = r.vehicle
    c = v.customer if v else None
    d = r.diagnosis
    wo = r.work_order
    checks = sorted(r.inspection_checks or [], key=lambda x: x.sort_order)
    status_label = {
        "ok": "OK",
        "watch": "Vigilar",
        "fail": "Falla",
        "na": "N/A",
    }

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
          <h2>Diagnóstico</h2>
          <p><strong>Técnico:</strong> {escape(d.technician or '')} ·
             <strong>Prioridad:</strong> {escape(d.priority or '')} ·
             <strong>Horas:</strong> {d.estimated_hours or 0}</p>
          <p><strong>Síntomas:</strong><br/>{escape(d.symptoms or '').replace(chr(10), '<br/>')}</p>
          <p><strong>Hallazgos:</strong><br/>{escape(d.findings or '').replace(chr(10), '<br/>')}</p>
          <p><strong>OBD:</strong> {escape(d.obd_codes or '—')}</p>
          <p><strong>Trabajo recomendado:</strong><br/>{escape(d.recommended_work or '').replace(chr(10), '<br/>')}</p>
        </div>"""
    else:
        diag_block = "<div class='box'><p>Sin diagnóstico guardado aún.</p></div>"

    plate = escape(v.plate if v else "")
    brand = escape(v.brand if v else "")
    model = escape(v.model if v else "")
    year = v.year if v else ""
    cname = escape(c.name if c else "")
    cphone = escape(c.phone if c else "")

    return f"""<!doctype html>
<html lang="es"><head>
<meta charset="utf-8"/>
<title>Diagnóstico {escape(r.code)} · Katire</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@700&family=Manrope:wght@400;600;700&display=swap');
  body{{font-family:Manrope,sans-serif;color:#0e1620;margin:0;padding:28px;background:#f7f1ea}}
  h1{{font-family:Unbounded,sans-serif;font-size:26px;margin:0;letter-spacing:-0.03em}}
  h2{{font-family:Unbounded,sans-serif;font-size:15px;margin:0 0 8px}}
  .tag{{color:#5a6a74;margin:4px 0 18px}}
  .box{{background:#fff;border:1px solid #d7e0e6;border-radius:12px;padding:14px 16px;margin:12px 0}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  th,td{{border-bottom:1px solid #e4ebef;padding:7px 6px;text-align:left}}
  th{{color:#5a6a74;font-size:11px;text-transform:uppercase;letter-spacing:0.06em}}
  .foot{{display:flex;justify-content:space-between;gap:24px;margin-top:36px;font-size:13px}}
  .line{{border-top:1px solid #9aa8b0;padding-top:8px;min-width:220px;margin-top:28px}}
  @media print{{body{{padding:12px;background:#fff}} .noprint{{display:none}}}}
</style>
</head><body>
  <button class="noprint" onclick="window.print()" style="padding:10px 14px;border-radius:10px;border:0;background:#ff4d2e;color:#fff;font-weight:700;cursor:pointer;margin-bottom:14px">Imprimir</button>
  <h1>Katire · Diagnóstico</h1>
  <p class="tag">{escape(shop_name)} · {escape(r.code)} · {escape(r.status)} · {escape((r.created_at.isoformat() if r.created_at else '')[:16])}</p>
  <div class="box">
    <p><strong>Vehículo:</strong> {plate} · {brand} {model} {year}<br/>
    <strong>Cliente:</strong> {cname} · {cphone}<br/>
    <strong>Queja:</strong> {escape(r.customer_complaint or '')}<br/>
    <strong>Km / combustible:</strong> {r.odometer_km} · {escape(r.fuel_level or '')}</p>
  </div>
  <div class="box">
    <h2>Daños al llegar</h2>
    <ul>{damages}</ul>
  </div>
  <div class="box">
    <h2>Lectura por sistemas</h2>
    <table><thead><tr><th>Sistema</th><th>Estado</th><th>Notas</th></tr></thead>
    <tbody>{dvi_rows}</tbody></table>
  </div>
  {diag_block}
  {wo_block}
  <div class="foot">
    <div class="line">Técnico<br/><strong>{escape((d.technician if d else '') or '')}</strong></div>
    <div class="line">Firma cliente<br/>&nbsp;</div>
  </div>
  <p class="tag" style="margin-top:28px">De la llave al XML. · Katire</p>
  <script>window.addEventListener('load',()=>{{ /* listo para imprimir */ }});</script>
</body></html>"""
