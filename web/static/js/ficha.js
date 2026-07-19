/* Ficha pro: DVI + cotización + portal cliente */

function carSvg(inspection) {
  const by = Object.fromEntries((inspection || []).map((i) => [i.system_key, i.status]));
  const cls = (k) => by[k] || "na";
  return `
  <svg class="car-svg" viewBox="0 0 200 320" xmlns="http://www.w3.org/2000/svg" aria-label="Mapa DVI">
    <rect class="zone ${cls("luces")}" data-key="luces" x="70" y="18" width="60" height="22" rx="6"/>
    <rect class="zone ${cls("carroceria")}" data-key="carroceria" x="45" y="48" width="110" height="90" rx="18"/>
    <rect class="zone ${cls("motor")}" data-key="motor" x="60" y="55" width="80" height="40" rx="8"/>
    <rect class="zone ${cls("aire")}" data-key="aire" x="70" y="100" width="60" height="28" rx="6"/>
    <rect class="zone ${cls("direccion")}" data-key="direccion" x="55" y="145" width="40" height="36" rx="8"/>
    <rect class="zone ${cls("electrico")}" data-key="electrico" x="105" y="145" width="40" height="36" rx="8"/>
    <rect class="zone ${cls("transmision")}" data-key="transmision" x="70" y="188" width="60" height="30" rx="6"/>
    <rect class="zone ${cls("suspension")}" data-key="suspension" x="40" y="188" width="24" height="55" rx="6"/>
    <rect class="zone ${cls("suspension")}" data-key="suspension" x="136" y="188" width="24" height="55" rx="6"/>
    <rect class="zone ${cls("frenos")}" data-key="frenos" x="38" y="250" width="28" height="28" rx="8"/>
    <rect class="zone ${cls("frenos")}" data-key="frenos" x="134" y="250" width="28" height="28" rx="8"/>
    <rect class="zone ${cls("llantas")}" data-key="llantas" x="36" y="282" width="32" height="22" rx="8"/>
    <rect class="zone ${cls("llantas")}" data-key="llantas" x="132" y="282" width="32" height="22" rx="8"/>
    <rect class="zone ${cls("escape")}" data-key="escape" x="85" y="250" width="30" height="40" rx="6"/>
    <rect class="zone ${cls("fluidos")}" data-key="fluidos" x="78" y="70" width="44" height="18" rx="5"/>
    <text x="100" y="160" text-anchor="middle" fill="#9bb0b8" font-size="11" font-family="Manrope,sans-serif">DVI</text>
  </svg>`;
}

async function openReception(id) {
  const ex = typeof esc === "function" ? esc : (s) => String(s ?? "");
  try {
  const r = await api(`/api/receptions/${id}`);
  const v = r.vehicle || {};
  const c = v.customer || {};
  const d = r.diagnosis || {};
  const wo = r.work_order;
  const est = r.estimate;
  const inspection = r.inspection || [];
  const dvi = r.dvi_summary || {};
  const publicUrl = (r.public_url || "").startsWith("http")
    ? r.public_url
    : `${location.origin}${r.public_url || ""}`;
  let parts = [];
  let services = [];
  let history = [];
  try {
    parts = await api(`/api/parts/lookup?brand=${encodeURIComponent(v.brand || "")}&model=${encodeURIComponent(v.model || "")}`);
  } catch (_) {}
  try { services = await api("/api/services"); } catch (_) {}
  try { if (v.id) history = await api(`/api/vehicles/${v.id}/history`); } catch (_) {}

  openModal(`
    <div class="panel-head">
      <div>
        <p class="muted" style="margin:0 0 6px;letter-spacing:0.14em;text-transform:uppercase;font-size:0.7rem;color:var(--lagoon)">Katire · expediente digital</p>
        <h2 style="margin:0;font-family:var(--display);letter-spacing:-0.03em">${ex(v.plate)} · ${ex(v.brand)} ${ex(v.model)}</h2>
        <p class="muted" style="margin:6px 0 0">${ex(r.code)} · ${ex(c.name || "")} · ${ex(c.phone || "")} · ${badge(r.status)}
          · DVI <span class="badge badge-ok">${dvi.ok || 0} ok</span>
          <span class="badge badge-en_diagnostico">${dvi.watch || 0} watch</span>
          <span class="badge badge-low">${dvi.fail || 0} fail</span>
        </p>
      </div>
      <div class="row-actions">
        <button class="btn btn-ghost" id="copyLink">Link cliente</button>
        <button class="btn btn-ghost" id="closeModalBtn">Cerrar</button>
      </div>
    </div>

    <div class="link-box">
      <span class="muted">Portal del cliente (como Shopmonkey/Tekmetric):</span>
      <code id="publicLink">${publicUrl}</code>
      <button class="btn btn-primary" id="openTrack">Abrir</button>
      <button class="btn btn-ok" id="makeEstimate">Generar / enviar cotización</button>
    </div>

    <div class="grid-2" style="margin-top:14px">
      <div>
        <div class="panel" style="box-shadow:none;border:1px solid var(--line)">
          <h3>Inspección digital (DVI)</h3>
          <p class="muted" style="margin-top:0">Semáforo por sistema — toque el mapa o los botones. Verde / amarillo / rojo.</p>
          <div class="dvi-map">
            ${carSvg(inspection)}
            <div class="dvi-items" id="dviItems">
              ${inspection.map((item) => `
                <div class="dvi-item" data-key="${item.system_key}">
                  <div>
                    <strong>${item.system_name}</strong>
                    <input class="dvi-note" data-key="${item.system_key}" value="${(item.notes || "").replaceAll('"', "&quot;")}" placeholder="Nota técnica..." style="margin-top:6px" />
                  </div>
                  <div class="dvi-actions">
                    <button type="button" data-status="ok" data-key="${item.system_key}" class="${item.status === "ok" ? "on-ok" : ""}">OK</button>
                    <button type="button" data-status="watch" data-key="${item.system_key}" class="${item.status === "watch" ? "on-watch" : ""}">Ver</button>
                    <button type="button" data-status="fail" data-key="${item.system_key}" class="${item.status === "fail" ? "on-fail" : ""}">Fail</button>
                  </div>
                </div>`).join("")}
            </div>
          </div>
          <div class="row-actions" style="margin-top:12px">
            <button class="btn btn-primary" id="saveDvi">Guardar inspección</button>
          </div>
        </div>

        <div class="panel" style="box-shadow:none;border:1px solid var(--line);margin-top:12px">
          <h3>Fotos + daños al llegar</h3>
          <div class="photo-grid">
            ${(r.photos || []).map((p) => `<figure><img src="${p.url}" alt=""/><figcaption>${p.zone || p.caption || ""}</figcaption></figure>`).join("")}
          </div>
          <form id="photoForm" class="row-actions" style="margin-top:12px">
            <input type="file" name="file" accept="image/*" required />
            <input name="zone" placeholder="Zona" style="max-width:140px" />
            <button class="btn btn-primary" type="submit">Subir foto</button>
          </form>
          <div style="margin-top:12px">
            ${(r.damages || []).map((x) => `<div style="margin-bottom:6px"><strong>${x.zone}</strong> · ${x.severity} — <span class="muted">${x.description || ""}</span></div>`).join("") || "<span class='muted'>Sin daños marcados en ingreso</span>"}
          </div>
        </div>

        <div class="panel" style="box-shadow:none;border:1px solid var(--line);margin-top:12px">
          <h3>Historial del vehículo</h3>
          ${history.slice(0, 6).map((h) => `
            <div style="padding:8px 0;border-bottom:1px solid var(--line)">
              <strong>${h.code}</strong> · ${badge(h.status)} · ${money(h.work_order_total)}
              <div class="muted">${h.created_at ? new Date(h.created_at).toLocaleDateString("es-CR") : ""} · ${h.complaint || ""}</div>
            </div>`).join("") || "<p class='muted'>Primera visita en bahía</p>"}
        </div>
      </div>

      <div>
        <div class="panel" style="box-shadow:none;border:1px solid var(--line)">
          <h3>Diagnóstico + OT</h3>
          <form id="diagForm" class="stack">
            <label>Técnico<input name="technician" value="${ex(d.technician || user()?.name || "")}" /></label>
            <label>Síntomas<textarea name="symptoms">${ex(d.symptoms || r.customer_complaint || "")}</textarea></label>
            <label>Hallazgos<textarea name="findings">${ex(d.findings || "")}</textarea></label>
            <label>OBD<input name="obd_codes" value="${ex(d.obd_codes || "")}" placeholder="P0301..." /></label>
            <label>Trabajo recomendado<textarea name="recommended_work">${ex(d.recommended_work || "")}</textarea></label>
            <div class="form-grid">
              <label>Horas<input name="estimated_hours" type="number" step="0.5" value="${d.estimated_hours || 1}" /></label>
              <label>Prioridad
                <select name="priority">
                  <option>normal</option><option ${d.priority === "alta" ? "selected" : ""}>alta</option><option ${d.priority === "urgente" ? "selected" : ""}>urgente</option>
                </select>
              </label>
            </div>
            <button class="btn btn-primary" type="submit">Guardar y crear OT</button>
          </form>
        </div>

        <div class="panel" style="box-shadow:none;border:1px solid var(--line);margin-top:12px">
          <h3>Servicios rápidos</h3>
          <div class="row-actions">
            ${services.slice(0, 6).map((s) => `
              <button class="btn btn-ghost btn-svc" data-sid="${s.id}" ${wo ? "" : "disabled"}>${s.name}</button>
            `).join("") || "<span class='muted'>Sin catálogo</span>"}
          </div>
        </div>

        <div class="panel" style="box-shadow:none;border:1px solid var(--line);margin-top:12px">
          <h3>Estantería viva</h3>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Pieza</th><th>Stock</th><th>Precio</th><th></th></tr></thead>
              <tbody>
                ${parts.slice(0, 8).map((p) => `<tr>
                  <td>${p.name}<br><span class="muted">${p.sku}</span></td>
                  <td>${p.stock_qty <= 0 ? `<span class="badge badge-low">0</span>` : `<span class="badge badge-ok">${p.stock_qty}</span>`}</td>
                  <td class="money">${money(p.sale_price)}</td>
                  <td><button class="btn btn-primary btn-add-part" data-part="${p.id}" ${wo ? "" : "disabled"}>${p.stock_qty > 0 ? "Usar" : "Pedir"}</button></td>
                </tr>`).join("") || `<tr><td colspan="4" class="muted">Sin coincidencias</td></tr>`}
              </tbody>
            </table>
          </div>
          ${wo ? `
            <div style="margin-top:14px">
              <h3>OT ${wo.code}</h3>
              <p class="muted">MO ${money(wo.labor_total)} · Piezas ${money(wo.parts_total)} · <strong>Total ${money(wo.grand_total)}</strong> · Cobro ${badge(wo.payment_status || "pendiente")}</p>
              <ul>${(wo.lines || []).map((l) => `<li>${l.description} × ${l.quantity} · ${badge(l.status)} · ${money(l.line_total)}</li>`).join("") || "<li class='muted'>Sin líneas</li>"}</ul>
              <div class="row-actions">
                <button class="btn btn-warn" id="statusRepair">En reparación</button>
                <button class="btn btn-ok" id="statusReady">Listo</button>
                <button class="btn btn-primary" id="statusDeliver">Entregar</button>
                <button class="btn btn-ok" id="btnSinpe">Cierre en colones</button>
                <button class="btn btn-ghost" id="btnMarkPaid">Marcar pagado</button>
                <button class="btn btn-primary" id="btnFacturar">Facturar CR</button>
              </div>
            </div>` : ""}
          ${est ? `<div style="margin-top:14px"><h3>Cotización ${est.code}</h3><p>${badge(est.status)} · ${money(est.grand_total)}</p></div>` : ""}
        </div>
      </div>
    </div>
  `);

  const state = Object.fromEntries(inspection.map((i) => [i.system_key, { ...i }]));

  document.getElementById("closeModalBtn").onclick = closeModal;
  document.getElementById("openTrack").onclick = () => window.open(publicUrl, "_blank");
  document.getElementById("copyLink").onclick = async () => {
    await navigator.clipboard.writeText(publicUrl);
    toast("Link del cliente copiado — péguelo en WhatsApp");
  };

  const paint = () => {
    document.querySelectorAll(".car-svg .zone").forEach((el) => {
      const k = el.dataset.key;
      el.classList.remove("ok", "watch", "fail", "na");
      el.classList.add(state[k]?.status || "na");
    });
  };

  document.querySelectorAll(".dvi-actions button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.key;
      const status = btn.dataset.status;
      if (state[key]) state[key].status = status;
      document.querySelectorAll(`.dvi-actions button[data-key="${key}"]`).forEach((b) => {
        b.classList.remove("on-ok", "on-watch", "on-fail");
      });
      btn.classList.add(`on-${status}`);
      paint();
    });
  });
  document.querySelectorAll(".car-svg .zone").forEach((el) => {
    el.addEventListener("click", () => {
      const key = el.dataset.key;
      if (!state[key]) return;
      const cycle = { na: "ok", ok: "watch", watch: "fail", fail: "na" };
      state[key].status = cycle[state[key].status] || "ok";
      const btn = document.querySelector(`.dvi-actions button[data-key="${key}"][data-status="${state[key].status}"]`);
      document.querySelectorAll(`.dvi-actions button[data-key="${key}"]`).forEach((b) => b.classList.remove("on-ok", "on-watch", "on-fail"));
      btn?.classList.add(`on-${state[key].status}`);
      paint();
      document.querySelector(`.dvi-item[data-key="${key}"]`)?.scrollIntoView({ block: "nearest" });
    });
  });

  document.getElementById("saveDvi").onclick = async () => {
    document.querySelectorAll(".dvi-note").forEach((inp) => {
      if (state[inp.dataset.key]) state[inp.dataset.key].notes = inp.value;
    });
    await api(`/api/receptions/${id}/inspection`, {
      method: "PUT",
      body: JSON.stringify({ items: Object.values(state) }),
    });
    toast("Inspección DVI guardada");
    openReception(id);
    loadDashboard();
  };

  document.getElementById("makeEstimate").onclick = async () => {
    const res = await api(`/api/receptions/${id}/estimate`, { method: "POST", body: "{}" });
    toast(res.message || "Cotización lista");
    await navigator.clipboard.writeText(`${location.origin}${res.public_url}`);
    toast("Link de cotización copiado para WhatsApp");
    openReception(id);
    loadDashboard();
  };

  document.getElementById("photoForm").onsubmit = async (e) => {
    e.preventDefault();
    await api(`/api/receptions/${id}/photos`, { method: "POST", body: new FormData(e.target), headers: {} });
    toast("Foto cargada");
    openReception(id);
  };

  document.getElementById("diagForm").onsubmit = async (e) => {
    e.preventDefault();
    try {
      const body = Object.fromEntries(new FormData(e.target).entries());
      body.estimated_hours = Number(body.estimated_hours || 1);
      body.create_work_order = true;
      await api(`/api/receptions/${id}/diagnosis`, { method: "POST", body: JSON.stringify(body) });
      toast("Diagnóstico + OT listos");
      openReception(id);
      loadDashboard();
      loadTaller();
    } catch (err) {
      toast(err.message || "No se pudo guardar el diagnóstico");
    }
  };

  document.querySelectorAll(".btn-add-part").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!wo) return;
      const result = await api(`/api/work-orders/${wo.id}/lines`, {
        method: "POST",
        body: JSON.stringify({ part_id: Number(btn.dataset.part), quantity: 1, description: "repuesto" }),
      });
      toast(result.message || "Listo");
      openReception(id);
      loadParts();
      loadSuppliers();
      loadDashboard();
    });
  });

  document.querySelectorAll(".btn-svc").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!wo) return;
      await api(`/api/work-orders/${wo.id}/add-service`, {
        method: "POST",
        body: JSON.stringify({ service_id: Number(btn.dataset.sid), work_order_id: wo.id }),
      });
      toast("Servicio agregado a la OT");
      openReception(id);
    });
  });

  const patchStatus = async (status) => {
    await api(`/api/receptions/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) });
    toast(`Estado: ${status.replaceAll("_", " ")}`);
    openReception(id);
    loadDashboard();
    loadTaller();
  };
  document.getElementById("statusRepair")?.addEventListener("click", () => patchStatus("en_reparacion"));
  document.getElementById("statusReady")?.addEventListener("click", () => patchStatus("listo"));
  document.getElementById("statusDeliver")?.addEventListener("click", () => patchStatus("entregado"));
  document.getElementById("btnFacturar")?.addEventListener("click", async () => {
    if (!wo) return;
    try {
      const inv = await api("/api/fe/issue", {
        method: "POST",
        body: JSON.stringify({
          work_order_id: wo.id,
          tipo_documento: "01",
          condicion_venta: "01",
          medio_pago: "06",
          tarifa_codigo: "08",
        }),
      });
      toast(`Factura ${inv.clave} generada`);
      const res = await fetch(`/api/fe/invoices/${inv.id}/print`, {
        headers: { Authorization: `Bearer ${token()}` },
      });
      const html = await res.text();
      const w = window.open("", "_blank");
      w.document.write(html);
      w.document.close();
    } catch (err) {
      toast(err.message);
    }
  });
  document.getElementById("btnSinpe")?.addEventListener("click", async () => {
    if (!wo) return;
    if (typeof openSinpeCobro === "function") {
      await openSinpeCobro({ work_order_id: wo.id });
      openReception(id);
    } else {
      toast("Recargue la página para cobro SINPE");
    }
  });
  document.getElementById("btnMarkPaid")?.addEventListener("click", async () => {
    if (!wo) return;
    try {
      await api(`/api/work-orders/${wo.id}/mark-paid`, { method: "POST", body: "{}" });
      toast("Marcado como pagado");
      openReception(id);
      loadDashboard();
    } catch (err) {
      toast(err.message);
    }
  });
  } catch (err) {
    toast(err.message || "No se pudo abrir la ficha");
  }
}
