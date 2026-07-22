"""Documentos imprimibles Katire (diagnóstico / croqui DVI + firma)."""

from __future__ import annotations

from html import escape

from app.models import Reception

_FILL = {
    "ok": "#7dcea0",
    "watch": "#f0c35a",
    "fail": "#ff6b7a",
    "na": "#d5dde3",
}


def _st(by: dict, key: str) -> str:
    return _FILL.get(by.get(key, "na"), _FILL["na"])


def _car_map_svg(checks: list) -> str:
    by = {c.system_key: c.status for c in checks}

    def z(key: str, shape: str, label: str, lx: float, ly: float) -> str:
        fill = _st(by, key)
        return (
            f'<g>'
            f'{shape.replace("FILL", fill)}'
            f'<text x="{lx}" y="{ly}" text-anchor="middle" font-size="8" '
            f'font-family="Manrope,sans-serif" fill="#0e1620" font-weight="700">{escape(label)}</text>'
            f'</g>'
        )

    parts = [
        # silueta
        '<path d="M70 40 Q140 8 210 40 L230 90 Q248 140 248 220 L248 360 '
        'Q248 430 220 470 Q140 505 60 470 Q32 430 32 360 L32 220 Q32 140 50 90 Z" '
        'fill="#e8eef2" stroke="#334155" stroke-width="2"/>',
        '<path d="M78 175 L202 175 L190 250 L90 250 Z" fill="#c5d4de" stroke="#334155" stroke-width="1"/>',
        '<path d="M90 310 L190 310 L200 360 L80 360 Z" fill="#c5d4de" stroke="#334155" stroke-width="1"/>',
        z("frente", '<path d="M78 28 Q140 6 202 28 L218 70 L62 70 Z" fill="FILL" stroke="#334155"/>', "FRENTE", 140, 52),
        z(
            "luces",
            '<rect x="58" y="62" width="36" height="22" rx="5" fill="FILL" stroke="#334155"/>'
            '<rect x="186" y="62" width="36" height="22" rx="5" fill="FILL" stroke="#334155"/>',
            "LUCES",
            140,
            78,
        ),
        z("capot", '<rect x="70" y="88" width="140" height="48" rx="8" fill="FILL" stroke="#334155"/>', "CAPÓ", 140, 116),
        z("motor", '<rect x="88" y="98" width="104" height="32" rx="6" fill="FILL" stroke="#334155"/>', "MOTOR", 140, 118),
        z("fluidos", '<rect x="96" y="132" width="88" height="18" rx="4" fill="FILL" stroke="#334155"/>', "FLUIDOS", 140, 145),
        z(
            "parabrisas",
            '<path d="M78 155 L202 155 L192 190 L88 190 Z" fill="FILL" stroke="#334155"/>',
            "PARABRISAS",
            140,
            178,
        ),
        z("techo", '<rect x="88" y="198" width="104" height="52" rx="8" fill="FILL" stroke="#334155"/>', "TECHO", 140, 228),
        z("aire", '<rect x="100" y="208" width="80" height="20" rx="4" fill="FILL" stroke="#334155"/>', "A/C", 140, 222),
        z("interior", '<rect x="96" y="232" width="88" height="36" rx="6" fill="FILL" stroke="#334155"/>', "INTERIOR", 140, 254),
        z("direccion", '<rect x="100" y="272" width="42" height="28" rx="5" fill="FILL" stroke="#334155"/>', "DIR.", 121, 290),
        z("electrico", '<rect x="148" y="272" width="42" height="28" rx="5" fill="FILL" stroke="#334155"/>', "ELEC.", 169, 290),
        z(
            "transmision",
            '<rect x="108" y="308" width="64" height="28" rx="6" fill="FILL" stroke="#334155"/>',
            "CAJA",
            140,
            326,
        ),
        z(
            "suspension",
            '<rect x="52" y="330" width="30" height="70" rx="6" fill="FILL" stroke="#334155"/>'
            '<rect x="198" y="330" width="30" height="70" rx="6" fill="FILL" stroke="#334155"/>',
            "SUSP.",
            140,
            360,
        ),
        z(
            "frenos",
            '<circle cx="55" cy="150" r="16" fill="FILL" stroke="#334155"/>'
            '<circle cx="225" cy="150" r="16" fill="FILL" stroke="#334155"/>'
            '<circle cx="55" cy="380" r="16" fill="FILL" stroke="#334155"/>'
            '<circle cx="225" cy="380" r="16" fill="FILL" stroke="#334155"/>',
            "FRENOS",
            140,
            400,
        ),
        z(
            "llantas",
            '<ellipse cx="38" cy="150" rx="12" ry="24" fill="FILL" stroke="#334155"/>'
            '<ellipse cx="242" cy="150" rx="12" ry="24" fill="FILL" stroke="#334155"/>'
            '<ellipse cx="38" cy="380" rx="12" ry="24" fill="FILL" stroke="#334155"/>'
            '<ellipse cx="242" cy="380" rx="12" ry="24" fill="FILL" stroke="#334155"/>',
            "LLANTAS",
            140,
            420,
        ),
        z(
            "lateral_izq",
            '<path d="M34 120 L62 110 L62 400 L34 390 Z" fill="FILL" stroke="#334155"/>',
            "IZQ",
            48,
            260,
        ),
        z(
            "lateral_der",
            '<path d="M218 110 L246 120 L246 390 L218 400 Z" fill="FILL" stroke="#334155"/>',
            "DER",
            232,
            260,
        ),
        z("escape", '<rect x="122" y="430" width="36" height="28" rx="5" fill="FILL" stroke="#334155"/>', "ESCAPE", 140, 448),
        z(
            "trasera",
            '<path d="M70 455 Q140 492 210 455 L218 430 L62 430 Z" fill="FILL" stroke="#334155"/>',
            "TRASERA",
            140,
            462,
        ),
        z(
            "carroceria",
            '<rect x="108" y="348" width="64" height="22" rx="5" fill="FILL" stroke="#334155"/>',
            "CARROCERÍA",
            140,
            363,
        ),
        '<text x="140" y="18" text-anchor="middle" font-size="9" fill="#5a6a74">↑ FRENTE</text>',
        '<text x="140" y="512" text-anchor="middle" font-size="9" fill="#5a6a74">TRASERA ↓</text>',
    ]
    return (
        '<svg viewBox="0 0 280 520" width="220" height="408" xmlns="http://www.w3.org/2000/svg" '
        'style="border:1px solid #d7e0e6;border-radius:12px;background:#f4f7f9">'
        + "".join(parts)
        + "</svg>"
    )


def diagnosis_print_html(r: Reception, shop_name: str = "Autorespuesto") -> str:
    v = r.vehicle
    c = v.customer if v else None
    d = r.diagnosis
    wo = r.work_order
    checks = sorted(r.inspection_checks or [], key=lambda x: x.sort_order or 0)
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
    ) or "<tr><td colspan='3'>Sin fallas marcadas en el croqui</td></tr>"

    dvi_rows = "".join(
        f"<tr><td>{escape(ch.system_name)}</td><td>{escape(status_label.get(ch.status, ch.status))}</td>"
        f"<td>{escape(ch.notes or '')}</td></tr>"
        for ch in checks
    ) or "<tr><td colspan='3'>Sin lectura de piezas</td></tr>"

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
        diag_block = "<div class='box'><p>Croqui listo. Complete el diagnóstico en pantalla si aún no está.</p></div>"

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
<title>Croqui diagnóstico {escape(r.code)} · Autorespuesto</title>
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
  <h1>Katire · Croqui de diagnóstico</h1>
  <p class="tag">Katire · {escape(r.code)} · {escape(r.status)} · {escape((r.created_at.isoformat() if r.created_at else '')[:16])}</p>
  <div class="box">
    <p><strong>Vehículo:</strong> {plate} · {brand} {model} {year}<br/>
    <strong>Cliente:</strong> {cname} · {cphone}<br/>
    <strong>Queja:</strong> {escape(r.customer_complaint or '')}<br/>
    <strong>Km / combustible:</strong> {r.odometer_km} · {escape(r.fuel_level or '')}</p>
  </div>
  <div class="box">
    <h2>Croqui del vehículo (piezas marcadas)</h2>
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
    <h2>Lectura completa por piezas</h2>
    <table><thead><tr><th>Pieza / sistema</th><th>Estado</th><th>Notas</th></tr></thead>
    <tbody>{dvi_rows}</tbody></table>
  </div>
  {diag_block}
  {wo_block}
  <div class="box auth">
    <h2>Autorización del cliente</h2>
    <p>Declaro que me explicaron el diagnóstico (croqui marcado) y autorizo a <strong>{escape(shop_name)}</strong>
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
  <p class="tag" style="margin-top:28px">De la llave al XML. · Katire · Autorespuesto</p>
</body></html>"""
