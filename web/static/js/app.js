const ZONES = [
  "Frente", "Lateral izq.", "Lateral der.", "Trasera",
  "Techo", "Interior", "Motor", "Suspensión",
  "Frenos", "Eléctrico", "Llantas", "Otro",
];

const STATUS_COLS = [
  ["recibido", "En el patio"],
  ["en_diagnostico", "En lectura"],
  ["esperando_repuestos", "Esperando pieza"],
  ["en_reparacion", "En manos"],
  ["listo", "Listo para salir"],
];

const BRAND = "Katire";

const money = (n) =>
  new Intl.NumberFormat("es-CR", { style: "currency", currency: "CRC", maximumFractionDigits: 0 }).format(n || 0);

const toast = (msg) => {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 3500);
};

const token = () => localStorage.getItem("tp_token");
const user = () => JSON.parse(localStorage.getItem("tp_user") || "null");

async function api(path, options = {}) {
  const headers = options.headers || {};
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }
  if (token()) headers.Authorization = `Bearer ${token()}`;
  const res = await fetch(path, { ...options, headers });
  let data = null;
  const text = await res.text();
  try { data = text ? JSON.parse(text) : null; } catch { data = { detail: text }; }
  if (res.status === 401) {
    localStorage.clear();
    location.href = "/login";
    throw new Error("Sesión expirada");
  }
  if (!res.ok) {
    const detail = data?.detail;
    throw new Error(typeof detail === "string" ? detail : (detail?.[0]?.msg || "Error en la solicitud"));
  }
  return data;
}

function badge(status) {
  const label = String(status || "").replaceAll("_", " ");
  return `<span class="badge badge-${status}">${label}</span>`;
}

function showSection(name) {
  document.querySelectorAll(".section").forEach((s) => s.classList.remove("active"));
  document.querySelectorAll("#nav button").forEach((b) => b.classList.toggle("active", b.dataset.section === name));
  document.getElementById(`sec-${name}`)?.classList.add("active");
  if (name === "tablero") loadDashboard();
  if (name === "recepcion") loadReceptions();
  if (name === "taller") loadTaller();
  if (name === "bodega") loadParts();
  if (name === "proveedores") loadSuppliers();
  if (name === "config") loadSettings();
  if (name === "facturacion") loadFacturacion();
}

async function loadFacturacion() {
  const issuer = await api("/api/fe/issuer");
  const form = document.getElementById("issuerForm");
  if (form) {
    Object.keys(issuer).forEach((k) => {
      if (form[k] !== undefined && k !== "hacienda_password" && k !== "has_password" && k !== "has_cert" && k !== "id") {
        form[k].value = issuer[k] ?? "";
      }
    });
  }
  const rows = await api("/api/fe/invoices");
  document.getElementById("feBody").innerHTML = rows
    .map((inv) => `<tr>
      <td><code style="font-size:0.72rem">${inv.clave}</code><br><span class="muted">${inv.numero_consecutivo}</span></td>
      <td>${inv.tipo_documento}</td>
      <td class="money">${money(inv.total_comprobante)}</td>
      <td>${badge(inv.status)}<br><span class="muted">${inv.hacienda_status || ""}</span></td>
      <td class="row-actions">
        <button class="btn btn-ghost" data-xml="${inv.id}">XML</button>
        <button class="btn btn-ghost" data-print="${inv.id}">PDF</button>
        <button class="btn btn-primary" data-send="${inv.id}">Enviar</button>
      </td>
    </tr>`)
    .join("") || `<tr><td colspan="5"><div class="empty-state"><strong>Sin comprobantes</strong>Emita desde una OT lista</div></td></tr>`;

  document.querySelectorAll("[data-xml]").forEach((btn) => {
    btn.onclick = async () => {
      const res = await fetch(`/api/fe/invoices/${btn.dataset.xml}/xml`, {
        headers: { Authorization: `Bearer ${token()}` },
      });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `katire-${btn.dataset.xml}.xml`;
      a.click();
      URL.revokeObjectURL(url);
    };
  });
  document.querySelectorAll("[data-print]").forEach((btn) => {
    btn.onclick = async () => {
      const res = await fetch(`/api/fe/invoices/${btn.dataset.print}/print`, {
        headers: { Authorization: `Bearer ${token()}` },
      });
      const html = await res.text();
      const w = window.open("", "_blank");
      w.document.write(html);
      w.document.close();
    };
  });
  document.querySelectorAll("[data-send]").forEach((btn) => {
    btn.onclick = async () => {
      try {
        const res = await api(`/api/fe/invoices/${btn.dataset.send}/send`, { method: "POST", body: "{}" });
        toast(res.message || (res.ok ? "Enviado a Hacienda" : "Revise firma / credenciales"));
        loadFacturacion();
      } catch (err) {
        toast(err.message);
      }
    };
  });
}

function openModal(html) {
  document.getElementById("modalBody").innerHTML = html;
  document.getElementById("modal").classList.add("show");
}
function closeModal() {
  document.getElementById("modal").classList.remove("show");
  document.getElementById("modalBody").innerHTML = "";
}

function initZones() {
  const grid = document.getElementById("zoneGrid");
  grid.innerHTML = ZONES.map(
    (z) => `<button type="button" class="zone-chip" data-zone="${z}">${z}</button>`
  ).join("");
  grid.addEventListener("click", (e) => {
    const btn = e.target.closest(".zone-chip");
    if (btn) btn.classList.toggle("active");
  });
}

async function loadSettings() {
  const s = await api("/api/settings");
  document.getElementById("shopSlogan").textContent =
    s.slogan || "De la llave al XML.";
  const form = document.getElementById("settingsForm");
  if (!form) return;
  form.shop_name.value = s.shop_name || "";
  form.slogan.value = s.slogan || "";
  form.phone.value = s.phone || "";
  form.whatsapp.value = s.whatsapp || "";
  form.address.value = s.address || "";
  form.labor_rate.value = s.labor_rate || 0;

  try {
    const users = await api("/api/users");
    document.getElementById("usersBody").innerHTML = users
      .map((u) => `<tr><td>${u.name}</td><td>${u.username}</td><td>${u.role}</td></tr>`)
      .join("") || `<tr><td colspan="3" class="muted">Sin usuarios adicionales</td></tr>`;
  } catch (_) {
    document.getElementById("usersBody").innerHTML = `<tr><td colspan="3" class="muted">Solo el administrador ve el equipo</td></tr>`;
  }

  const services = await api("/api/services");
  document.getElementById("servicesBody").innerHTML = services
    .map((s) => `<tr><td>${s.name}</td><td>${s.category}</td><td>${s.hours}</td><td class="money">${money(s.price)}</td></tr>`)
    .join("") || `<tr><td colspan="4"><div class="empty-state"><strong>Planilla vacía</strong>Agregue los servicios reales de su taller</div></td></tr>`;
}

async function loadDashboard() {
  const d = await api("/api/dashboard");
  document.getElementById("metricsPro").innerHTML = `
    <div class="metric-card"><div class="k">Ingreso hoy</div><div class="v">${money(d.revenue_today)}</div><div class="s">Órdenes cerradas del día</div></div>
    <div class="metric-card"><div class="k">ARO</div><div class="v">${money(d.aro)}</div><div class="s">Ticket promedio (como Tekmetric)</div></div>
    <div class="metric-card"><div class="k">Conversión cotización</div><div class="v">${d.estimate_conversion_pct || 0}%</div><div class="s">${d.estimate_approved || 0} aprobadas / ${d.estimate_declined || 0} rechazadas</div></div>
    <div class="metric-card"><div class="k">Margen repuestos</div><div class="v">${d.parts_margin_pct || 0}%</div><div class="s">${money(d.parts_margin)} esta temporada</div></div>
  `;
  document.getElementById("stats").innerHTML = `
    <div class="stat"><div class="label">Entraron hoy</div><div class="value">${d.today_receptions}</div></div>
    <div class="stat"><div class="label">En el patio</div><div class="value">${d.in_shop}</div></div>
    <div class="stat"><div class="label">Listos</div><div class="value">${d.ready_for_delivery}</div></div>
    <div class="stat"><div class="label">Piezas en ruta</div><div class="value">${d.open_purchase_orders}</div></div>
    <div class="stat"><div class="label">Bajo mínimo</div><div class="value">${d.low_stock_count}</div></div>
  `;
  const kanban = document.getElementById("kanban");
  kanban.innerHTML = STATUS_COLS.map(([key, title]) => {
    const list = (d.board || []).filter((r) => r.status === key);
    const cards = list
      .map((r) => {
        const v = r.vehicle || {};
        return `<div class="card-job" data-id="${r.id}">
          <strong>${v.plate || "—"}</strong>
          <div class="meta">${v.brand || ""} ${v.model || ""}<br>${r.code}<br>${(r.customer_complaint || "").slice(0, 60)}</div>
        </div>`;
      })
      .join("") || `<div class="empty-state" style="padding:14px;border:none"><strong>Vacío</strong>Nadie en esta estación</div>`;
    return `<div class="kanban-col"><h4>${title}<span>${list.length}</span></h4>${cards}</div>`;
  }).join("");
  kanban.querySelectorAll(".card-job").forEach((el) => {
    el.addEventListener("click", () => openReception(Number(el.dataset.id)));
  });
  document.getElementById("lowStockBody").innerHTML = (d.low_stock || [])
    .map((p) => `<tr>
      <td>${p.sku}</td><td>${p.name}</td>
      <td><span class="badge badge-low">${p.stock_qty}</span></td>
      <td>${p.min_stock}</td><td>${p.preferred_supplier || "—"}</td>
    </tr>`)
    .join("") || `<tr><td colspan="5"><div class="empty-state"><strong>Estantería firme</strong>Nada bajo el mínimo ahora</div></td></tr>`;

  document.getElementById("apptBody").innerHTML = (d.appointments || [])
    .map((a) => `<tr>
      <td>${new Date(a.starts_at).toLocaleString("es-CR")}</td>
      <td>${a.customer_name}<br><span class="muted">${a.phone || ""}</span></td>
      <td>${a.plate} ${a.vehicle_info || ""}</td>
      <td>${a.reason || "—"}</td>
      <td>${badge(a.status)}</td>
    </tr>`)
    .join("") || `<tr><td colspan="5"><div class="empty-state"><strong>Sin citas</strong>Planilla lista — agende la primera</div></td></tr>`;
}

async function loadReceptions() {
  const rows = await api("/api/receptions");
  document.getElementById("receptionList").innerHTML = rows
    .slice(0, 20)
    .map((r) => {
      const v = r.vehicle || {};
      return `<tr>
        <td>${r.code}</td>
        <td>${v.plate}<br><span class="muted">${v.brand} ${v.model}</span></td>
        <td>${badge(r.status)}</td>
        <td><button class="btn btn-ghost" data-id="${r.id}">Abrir</button></td>
      </tr>`;
    })
    .join("") || `<tr><td colspan="4"><div class="empty-state"><strong>Sin ingresos</strong>Planilla lista para el primer vehículo</div></td></tr>`;
  document.querySelectorAll("#receptionList [data-id]").forEach((btn) => {
    btn.addEventListener("click", () => openReception(Number(btn.dataset.id)));
  });
}

async function loadTaller() {
  const rows = await api("/api/receptions");
  document.getElementById("tallerList").innerHTML = rows
    .filter((r) => r.status !== "entregado")
    .map((r) => {
      const v = r.vehicle || {};
      const c = v.customer || {};
      return `<tr>
        <td>${r.code}</td>
        <td>${v.plate} · ${v.brand} ${v.model}</td>
        <td>${c.name || "—"}</td>
        <td>${badge(r.status)}</td>
        <td>${r.work_order?.code || "—"}</td>
        <td><button class="btn btn-primary" data-id="${r.id}">Diagnosticar / OT</button></td>
      </tr>`;
    })
    .join("") || `<tr><td colspan="6"><div class="empty-state"><strong>Patio libre</strong>Cuando ingrese un vehículo aparecerá aquí</div></td></tr>`;
  document.querySelectorAll("#tallerList [data-id]").forEach((btn) => {
    btn.addEventListener("click", () => openReception(Number(btn.dataset.id)));
  });
}

async function loadParts() {
  const q = document.getElementById("partSearch").value.trim();
  const low = document.getElementById("onlyLow").checked;
  const parts = await api(`/api/parts?q=${encodeURIComponent(q)}&low_stock=${low}`);
  document.getElementById("partsBody").innerHTML = parts
    .map((p) => `<tr>
      <td>${p.sku}</td>
      <td><strong>${p.name}</strong><br><span class="muted">${p.brand} · ${p.category}</span></td>
      <td>${p.compatible_with || "—"}</td>
      <td>${p.location || "—"}</td>
      <td>${p.low_stock ? `<span class="badge badge-low">${p.stock_qty}</span>` : `<span class="badge badge-ok">${p.stock_qty}</span>`}</td>
      <td class="money">${money(p.sale_price)}</td>
      <td>${p.preferred_supplier || "—"}</td>
      <td class="row-actions">
        <button class="btn btn-ghost" data-adjust="${p.id}">Ajuste</button>
      </td>
    </tr>`)
    .join("") || `<tr><td colspan="8"><div class="empty-state"><strong>Estantería vacía</strong>Registre sus repuestos reales (SKU, stock, proveedor)</div></td></tr>`;
  document.querySelectorAll("[data-adjust]").forEach((btn) => {
    btn.addEventListener("click", () => adjustPart(Number(btn.dataset.adjust)));
  });
}

async function loadSuppliers() {
  const [suppliers, orders] = await Promise.all([
    api("/api/suppliers"),
    api("/api/purchase-orders"),
  ]);
  document.getElementById("suppliersBody").innerHTML = suppliers
    .map((s) => `<tr><td>${s.name}</td><td>${s.city}</td><td>${s.phone}</td><td>${s.notes || ""}</td></tr>`)
    .join("") || `<tr><td colspan="4"><div class="empty-state"><strong>Sin proveedores</strong>Agregue su cadena real de repuestos</div></td></tr>`;
  document.getElementById("poBody").innerHTML = orders
    .map((po) => `<tr>
      <td>${po.code}<br><span class="muted">${(po.lines || []).map((l) => l.part_name).join(", ")}</span></td>
      <td>${po.supplier?.name || ""}</td>
      <td class="money">${money(po.total)}</td>
      <td>${badge(po.status)}</td>
      <td class="row-actions">
        ${po.status !== "recibido" ? `<button class="btn btn-ok" data-receive="${po.id}">Marcar recibido</button>` : "—"}
        ${po.status === "solicitado" ? `<button class="btn btn-warn" data-ship="${po.id}">En camino</button>` : ""}
      </td>
    </tr>`)
    .join("") || `<tr><td colspan="5"><div class="empty-state"><strong>Sin pedidos</strong>Se crean solos cuando falte stock en una OT</div></td></tr>`;
  document.querySelectorAll("[data-receive]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api(`/api/purchase-orders/${btn.dataset.receive}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: "recibido" }),
      });
      toast("Pedido recibido e inventariado");
      loadSuppliers();
      loadDashboard();
    });
  });
  document.querySelectorAll("[data-ship]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api(`/api/purchase-orders/${btn.dataset.ship}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: "en_camino" }),
      });
      toast("Pedido marcado en camino");
      loadSuppliers();
    });
  });
}

async function openReception(id) {
  const r = await api(`/api/receptions/${id}`);
  const v = r.vehicle || {};
  const c = v.customer || {};
  const d = r.diagnosis || {};
  const wo = r.work_order;
  const brand = v.brand || "";
  const model = v.model || "";
  let parts = [];
  try {
    parts = await api(`/api/parts/lookup?brand=${encodeURIComponent(brand)}&model=${encodeURIComponent(model)}`);
  } catch (_) {}

  openModal(`
    <div class="panel-head">
      <div>
        <p class="muted" style="margin:0 0 6px;letter-spacing:0.14em;text-transform:uppercase;font-size:0.7rem;color:var(--lagoon)">${BRAND} · ficha del patio</p>
        <h2 style="margin:0;font-family:var(--display);letter-spacing:-0.03em">${v.plate} · ${v.brand} ${v.model}</h2>
        <p class="muted" style="margin:6px 0 0">${r.code} · ${c.name || ""} · ${c.phone || ""} · ${badge(r.status)}</p>
      </div>
      <button class="btn btn-ghost" id="closeModalBtn">Cerrar</button>
    </div>

    <div class="grid-2">
      <div>
        <div class="panel" style="box-shadow:none;margin:0 0 12px;padding:0;border:none;background:transparent">
          <h3>Queja / ingreso</h3>
          <p>${r.customer_complaint || "—"}</p>
          <p class="muted">Combustible: ${r.fuel_level} · Km: ${r.odometer_km} · Firma: ${r.customer_signature_name || "—"}</p>
        </div>
        <div class="panel" style="box-shadow:none;border:1px solid var(--line)">
          <h3>Daños al llegar</h3>
          ${(r.damages || []).map((x) => `<div style="margin-bottom:8px"><strong>${x.zone}</strong> · ${x.severity}<br><span class="muted">${x.description || ""}</span></div>`).join("") || "<p class='muted'>Sin daños registrados</p>"}
          <div class="form-grid" style="margin-top:12px">
            <label>Zona
              <select id="dmgZone">${ZONES.map((z) => `<option>${z}</option>`).join("")}</select>
            </label>
            <label>Severidad
              <select id="dmgSev"><option>leve</option><option>medio</option><option>grave</option></select>
            </label>
            <label class="full">Descripción<input id="dmgDesc" /></label>
            <div class="full"><button class="btn btn-ghost" id="addDamage">Agregar daño</button></div>
          </div>
        </div>
        <div class="panel" style="box-shadow:none;border:1px solid var(--line);margin-top:12px">
          <h3>Fotos del vehículo</h3>
          <div class="photo-grid" id="photoGrid">
            ${(r.photos || []).map((p) => `<figure><img src="${p.url}" alt=""/><figcaption>${p.zone || p.caption || ""}</figcaption></figure>`).join("")}
          </div>
          <form id="photoForm" class="row-actions" style="margin-top:12px">
            <input type="file" name="file" accept="image/*" required />
            <input name="zone" placeholder="Zona" style="max-width:140px" />
            <button class="btn btn-primary" type="submit">Subir foto</button>
          </form>
        </div>
      </div>

      <div>
        <div class="panel" style="box-shadow:none;border:1px solid var(--line)">
          <h3>Diagnóstico guiado</h3>
          <form id="diagForm" class="stack">
            <label>Técnico<input name="technician" value="${d.technician || user()?.name || ""}" /></label>
            <label>Síntomas<textarea name="symptoms">${d.symptoms || r.customer_complaint || ""}</textarea></label>
            <label>Hallazgos del mecánico<textarea name="findings">${d.findings || ""}</textarea></label>
            <label>Códigos OBD (opcional)<input name="obd_codes" value="${d.obd_codes || ""}" placeholder="P0301, C1201..." /></label>
            <label>Trabajo recomendado<textarea name="recommended_work">${d.recommended_work || ""}</textarea></label>
            <div class="form-grid">
              <label>Horas estimadas<input name="estimated_hours" type="number" step="0.5" value="${d.estimated_hours || 1}" /></label>
              <label>Prioridad
                <select name="priority">
                  <option ${d.priority === "normal" ? "selected" : ""}>normal</option>
                  <option ${d.priority === "alta" ? "selected" : ""}>alta</option>
                  <option ${d.priority === "urgente" ? "selected" : ""}>urgente</option>
                </select>
              </label>
            </div>
            <button class="btn btn-primary" type="submit">Guardar diagnóstico y crear OT</button>
          </form>
        </div>

        <div class="panel" style="box-shadow:none;border:1px solid var(--line);margin-top:12px">
          <h3>Repuestos compatibles / bodega</h3>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Repuesto</th><th>Stock</th><th>Precio</th><th></th></tr></thead>
              <tbody>
                ${parts.slice(0, 8).map((p) => `<tr>
                  <td>${p.name}<br><span class="muted">${p.sku}</span></td>
                  <td>${p.low_stock || p.stock_qty <= 0 ? badge("esperando_repuestos").replace("esperando repuestos", p.stock_qty <= 0 ? "sin stock" : "bajo") : `<span class="badge badge-ok">${p.stock_qty}</span>`}</td>
                  <td class="money">${money(p.sale_price)}</td>
                  <td><button class="btn btn-primary btn-add-part" data-part="${p.id}" ${wo ? "" : "disabled title='Guarde el diagnóstico primero'"}>${p.stock_qty > 0 ? "Usar" : "Pedir"}</button></td>
                </tr>`).join("") || `<tr><td colspan="4" class="muted">Sin coincidencias. Busque en Bodega.</td></tr>`}
              </tbody>
            </table>
          </div>
          ${wo ? `
            <div style="margin-top:14px">
              <h3>Orden ${wo.code}</h3>
              <p class="muted">Mano de obra: ${money(wo.labor_total)} · Repuestos: ${money(wo.parts_total)} · <strong>Total ${money(wo.grand_total)}</strong></p>
              <ul>
                ${(wo.lines || []).map((l) => `<li>${l.description} × ${l.quantity} · ${badge(l.status)} · ${money(l.line_total)}</li>`).join("") || "<li class='muted'>Sin líneas aún</li>"}
              </ul>
              <div class="row-actions">
                <button class="btn btn-warn" id="statusRepair">En reparación</button>
                <button class="btn btn-ok" id="statusReady">Marcar listo</button>
                <button class="btn btn-primary" id="statusDeliver">Entregar al cliente</button>
              </div>
            </div>
          ` : `<p class="muted" style="margin-top:12px">Guarde el diagnóstico para generar la orden de trabajo y usar/pedir repuestos.</p>`}
        </div>
      </div>
    </div>
  `);

  document.getElementById("closeModalBtn").onclick = closeModal;

  document.getElementById("addDamage").onclick = async () => {
    const fd = new FormData();
    fd.append("zone", document.getElementById("dmgZone").value);
    fd.append("severity", document.getElementById("dmgSev").value);
    fd.append("description", document.getElementById("dmgDesc").value);
    await api(`/api/receptions/${id}/damages`, { method: "POST", body: fd, headers: {} });
    toast("Daño agregado");
    openReception(id);
  };

  document.getElementById("photoForm").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    await api(`/api/receptions/${id}/photos`, { method: "POST", body: fd, headers: {} });
    toast("Foto cargada");
    openReception(id);
  };

  document.getElementById("diagForm").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = Object.fromEntries(fd.entries());
    body.estimated_hours = Number(body.estimated_hours || 0);
    body.create_work_order = true;
    await api(`/api/receptions/${id}/diagnosis`, { method: "POST", body: JSON.stringify(body) });
    toast("Diagnóstico guardado y OT creada");
    openReception(id);
    loadDashboard();
    loadTaller();
  };

  document.querySelectorAll(".btn-add-part").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!wo) return;
      const result = await api(`/api/work-orders/${wo.id}/lines`, {
        method: "POST",
        body: JSON.stringify({ part_id: Number(btn.dataset.part), quantity: 1, description: "repuesto" }),
      });
      toast(result.message || "Repuesto procesado");
      openReception(id);
      loadParts();
      loadSuppliers();
      loadDashboard();
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

  const printBtn = document.createElement("button");
  printBtn.className = "btn btn-ghost";
  printBtn.textContent = "Imprimir ficha";
  printBtn.style.marginLeft = "8px";
  document.querySelector(".modal .panel-head > div")?.appendChild(printBtn);
  printBtn.onclick = () => {
    const w = window.open("", "_blank", "width=800,height=900");
    w.document.write(`<!doctype html><html><head><title>${BRAND} ${r.code}</title>
      <style>
        @import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@700&family=Manrope:wght@400;600&display=swap');
        body{font-family:Manrope,sans-serif;padding:36px;color:#0a121c;background:#f4faf8}
        .mark{font-family:Unbounded,sans-serif;font-size:28px;letter-spacing:-0.04em;margin:0}
        .mark i{font-style:normal;color:#149e84}
        .tag{color:#5a727a;margin:4px 0 20px;font-size:13px}
        h2{margin:0 0 4px;font-family:Unbounded,sans-serif;font-size:18px}
        .box{border:1px solid #cfe3dd;background:#fff;padding:14px 16px;margin-top:12px;border-radius:12px}
        .foot{margin-top:48px;display:flex;justify-content:space-between;gap:24px;font-size:13px}
        .line{border-top:1px solid #9bb0b8;margin-top:28px;padding-top:8px;min-width:220px}
      </style></head><body>
      <p class="mark">bah<i>í</i>a</p>
      <p class="tag">Ficha de ingreso · ${r.code} · ${new Date(r.created_at || Date.now()).toLocaleString("es-CR")}</p>
      <h2>${v.plate} · ${v.brand} ${v.model}</h2>
      <div class="box">
        <strong>Cliente:</strong> ${c.name || ""} · ${c.phone || ""}<br/>
        <strong>Vehículo:</strong> ${v.year || ""} · ${v.color || ""} · ${r.odometer_km} km · combustible ${r.fuel_level}<br/>
        <strong>Lo que presenta:</strong> ${r.customer_complaint || ""}
      </div>
      <div class="box"><strong>Daños al llegar</strong><ul>
        ${(r.damages || []).map((x) => `<li>${x.zone} (${x.severity}): ${x.description || ""}</li>`).join("") || "<li>Ninguno registrado</li>"}
      </ul></div>
      ${wo ? `<div class="box"><strong>Orden ${wo.code}</strong><br/>Total estimado: ${money(wo.grand_total)}<ul>
        ${(wo.lines || []).map((l) => `<li>${l.description} × ${l.quantity}</li>`).join("")}
      </ul></div>` : ""}
      <div class="foot">
        <div class="line">Firma quien entrega<br/><strong>${r.customer_signature_name || ""}</strong></div>
        <div class="line">Recibe el patio<br/><strong>${r.received_by || ""}</strong></div>
      </div>
      <script>window.print()</script></body></html>`);
    w.document.close();
  };
}

async function adjustPart(id) {
  const qty = prompt("Cantidad a sumar (use negativo para restar):", "1");
  if (qty === null) return;
  await api(`/api/parts/${id}/adjust`, {
    method: "POST",
    body: JSON.stringify({ quantity: Number(qty), movement_type: "ajuste", note: "Ajuste manual" }),
  });
  toast("Stock actualizado");
  loadParts();
}

function bindUI() {
  const u = user();
  if (!token() || !u) {
    location.href = "/login";
    return;
  }
  document.getElementById("userName").textContent = u.name;
  document.getElementById("userRole").textContent = u.role;
  document.getElementById("receivedBy").value = u.name;
  document.getElementById("logoutBtn").onclick = () => {
    localStorage.clear();
    location.href = "/login";
  };
  document.querySelectorAll("#nav button").forEach((btn) => {
    btn.addEventListener("click", () => showSection(btn.dataset.section));
  });
  document.querySelectorAll("[data-go]").forEach((btn) => {
    btn.addEventListener("click", () => showSection(btn.dataset.go));
  });
  document.getElementById("refreshBoard").onclick = loadDashboard;
  document.getElementById("partSearchBtn").onclick = loadParts;
  document.getElementById("onlyLow").onchange = loadParts;
  document.getElementById("partSearch").addEventListener("keydown", (e) => {
    if (e.key === "Enter") loadParts();
  });
  document.getElementById("modal").addEventListener("click", (e) => {
    if (e.target.id === "modal") closeModal();
  });

  document.getElementById("receptionForm").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const zones = [...document.querySelectorAll(".zone-chip.active")].map((el) => el.dataset.zone);
    const damageNotes = fd.get("damage_notes") || "";
    const body = {
      customer: {
        name: fd.get("customer_name"),
        phone: fd.get("customer_phone"),
        id_number: fd.get("customer_id_number"),
      },
      plate: String(fd.get("plate") || "").toUpperCase(),
      brand: fd.get("brand"),
      model: fd.get("model"),
      year: Number(fd.get("year") || 0),
      color: fd.get("color"),
      odometer_km: Number(fd.get("odometer_km") || 0),
      fuel_level: fd.get("fuel_level"),
      promised_hours: Number(fd.get("promised_hours") || 24),
      customer_complaint: fd.get("customer_complaint"),
      accessories: fd.get("accessories"),
      received_by: fd.get("received_by"),
      customer_signature_name: fd.get("customer_signature_name"),
      customer_accepted: fd.get("customer_accepted") === "on",
      damages: zones.map((zone) => ({
        zone,
        severity: "leve",
        description: damageNotes,
        present_on_arrival: true,
      })),
    };
    if (!body.damages.length && damageNotes) {
      body.damages = [{ zone: "Otro", severity: "leve", description: damageNotes, present_on_arrival: true }];
    }
    const created = await api("/api/receptions", { method: "POST", body: JSON.stringify(body) });
    toast(`Recepción ${created.code} creada`);
    e.target.reset();
    document.querySelectorAll(".zone-chip.active").forEach((el) => el.classList.remove("active"));
    document.getElementById("receivedBy").value = user().name;
    loadReceptions();
    loadDashboard();
    openReception(created.id);
  };

  document.getElementById("settingsForm").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = Object.fromEntries(fd.entries());
    body.labor_rate = Number(body.labor_rate || 0);
    await api("/api/settings", { method: "PUT", body: JSON.stringify(body) });
    toast("Configuración guardada");
    loadSettings();
  };

  document.getElementById("newPartBtn").onclick = async () => {
    openModal(`
      <h2>Nuevo repuesto</h2>
      <form id="partForm" class="form-grid">
        <label>SKU<input name="sku" required /></label>
        <label>Nombre<input name="name" required /></label>
        <label>Marca<input name="brand" /></label>
        <label>Categoría<input name="category" value="General" /></label>
        <label class="full">Compatibilidad<input name="compatible_with" placeholder="Toyota Corolla, Yaris..." /></label>
        <label>Ubicación bodega<input name="location" /></label>
        <label>Stock<input name="stock_qty" type="number" value="0" /></label>
        <label>Mínimo<input name="min_stock" type="number" value="1" /></label>
        <label>Costo<input name="cost_price" type="number" value="0" /></label>
        <label>Precio venta<input name="sale_price" type="number" value="0" /></label>
        <label class="full">ID proveedor preferido<input name="preferred_supplier_id" type="number" placeholder="Ver lista de proveedores" /></label>
        <div class="full row-actions">
          <button class="btn btn-primary" type="submit">Guardar</button>
          <button class="btn btn-ghost" type="button" id="closeModalBtn">Cancelar</button>
        </div>
      </form>
    `);
    document.getElementById("closeModalBtn").onclick = closeModal;
    document.getElementById("partForm").onsubmit = async (ev) => {
      ev.preventDefault();
      const fd = new FormData(ev.target);
      const body = Object.fromEntries(fd.entries());
      ["stock_qty", "min_stock", "cost_price", "sale_price"].forEach((k) => (body[k] = Number(body[k] || 0)));
      body.preferred_supplier_id = body.preferred_supplier_id ? Number(body.preferred_supplier_id) : null;
      await api("/api/parts", { method: "POST", body: JSON.stringify(body) });
      toast("Repuesto creado");
      closeModal();
      loadParts();
    };
  };

  document.getElementById("issuerForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.target).entries());
    if (!body.hacienda_password) delete body.hacienda_password;
    await api("/api/fe/issuer", { method: "PUT", body: JSON.stringify(body) });
    toast("Emisor Hacienda guardado");
    loadFacturacion();
  });

  document.getElementById("testHaciendaBtn")?.addEventListener("click", async () => {
    try {
      const res = await api("/api/fe/test-auth", { method: "POST", body: "{}" });
      toast(`Auth Hacienda OK (${res.environment})`);
    } catch (err) {
      toast(err.message);
    }
  });

  document.getElementById("issueFeBtn")?.addEventListener("click", async () => {
    const taller = await api("/api/receptions");
    const withOt = taller.filter((r) => r.work_order);
    if (!withOt.length) {
      toast("Primero cree una OT en Diagnóstico");
      return;
    }
    openModal(`
      <h2>Emitir comprobante Katire</h2>
      <form id="feIssueForm" class="form-grid">
        <label class="full">Orden de trabajo
          <select name="work_order_id" required>
            ${withOt.map((r) => `<option value="${r.work_order.id}">${r.work_order.code} · ${r.vehicle?.plate || ""} · ${money(r.work_order.grand_total)}</option>`).join("")}
          </select>
        </label>
        <label>Tipo
          <select name="tipo_documento">
            <option value="01">01 Factura Electrónica</option>
            <option value="04">04 Tiquete Electrónico</option>
            <option value="03">03 Nota de Crédito</option>
          </select>
        </label>
        <label>IVA
          <select name="tarifa_codigo">
            <option value="08">13% general</option>
            <option value="04">4%</option>
            <option value="03">2%</option>
            <option value="02">1%</option>
            <option value="01">Exento</option>
          </select>
        </label>
        <label>Condición
          <select name="condicion_venta">
            <option value="01">Contado</option>
            <option value="02">Crédito</option>
          </select>
        </label>
        <label>Medio pago
          <select name="medio_pago">
            <option value="01">Efectivo</option>
            <option value="02">Tarjeta</option>
            <option value="04">Transferencia</option>
            <option value="06">SINPE Móvil</option>
          </select>
        </label>
        <div class="full row-actions">
          <button class="btn btn-primary" type="submit">Generar XML + clave</button>
          <button class="btn btn-ghost" type="button" id="closeModalBtn">Cancelar</button>
        </div>
      </form>
    `);
    document.getElementById("closeModalBtn").onclick = closeModal;
    document.getElementById("feIssueForm").onsubmit = async (ev) => {
      ev.preventDefault();
      const body = Object.fromEntries(new FormData(ev.target).entries());
      body.work_order_id = Number(body.work_order_id);
      const inv = await api("/api/fe/issue", { method: "POST", body: JSON.stringify(body) });
      toast(`Comprobante ${inv.clave.slice(0, 12)}… listo`);
      closeModal();
      loadFacturacion();
      showSection("facturacion");
    };
  });

  document.getElementById("newUserBtn")?.addEventListener("click", () => {
    openModal(`
      <h2>Nuevo usuario</h2>
      <form id="userForm" class="form-grid">
        <label>Nombre<input name="name" required /></label>
        <label>Usuario<input name="username" required /></label>
        <label>Clave<input name="password" type="password" required /></label>
        <label>Rol
          <select name="role">
            <option value="recepcion">recepcion</option>
            <option value="mecanico">mecanico</option>
            <option value="admin">admin</option>
          </select>
        </label>
        <div class="full row-actions">
          <button class="btn btn-primary" type="submit">Crear</button>
          <button class="btn btn-ghost" type="button" id="closeModalBtn">Cancelar</button>
        </div>
      </form>
    `);
    document.getElementById("closeModalBtn").onclick = closeModal;
    document.getElementById("userForm").onsubmit = async (ev) => {
      ev.preventDefault();
      const body = Object.fromEntries(new FormData(ev.target).entries());
      await api("/api/users", { method: "POST", body: JSON.stringify(body) });
      toast("Usuario creado");
      closeModal();
      loadSettings();
    };
  });

  document.getElementById("newServiceBtn")?.addEventListener("click", () => {
    openModal(`
      <h2>Nuevo servicio</h2>
      <form id="svcForm" class="form-grid">
        <label class="full">Nombre<input name="name" required placeholder="Ej. Cambio de aceite" /></label>
        <label>Categoría<input name="category" value="General" /></label>
        <label>Horas<input name="hours" type="number" step="0.25" value="1" /></label>
        <label>Precio (CRC)<input name="price" type="number" value="0" /></label>
        <label class="full">Descripción<textarea name="description"></textarea></label>
        <div class="full row-actions">
          <button class="btn btn-primary" type="submit">Guardar</button>
          <button class="btn btn-ghost" type="button" id="closeModalBtn">Cancelar</button>
        </div>
      </form>
    `);
    document.getElementById("closeModalBtn").onclick = closeModal;
    document.getElementById("svcForm").onsubmit = async (ev) => {
      ev.preventDefault();
      const body = Object.fromEntries(new FormData(ev.target).entries());
      body.hours = Number(body.hours || 0);
      body.price = Number(body.price || 0);
      await api("/api/services", { method: "POST", body: JSON.stringify(body) });
      toast("Servicio agregado al catálogo");
      closeModal();
      loadSettings();
    };
  });

  document.getElementById("newApptBtn")?.addEventListener("click", async () => {
    openModal(`
      <h2>Agendar cita</h2>
      <form id="apptForm" class="form-grid">
        <label>Cliente<input name="customer_name" required /></label>
        <label>WhatsApp<input name="phone" /></label>
        <label>Placa<input name="plate" style="text-transform:uppercase" /></label>
        <label>Vehículo<input name="vehicle_info" placeholder="Toyota Corolla 2018" /></label>
        <label class="full">Cuándo<input name="starts_at" type="datetime-local" required /></label>
        <label class="full">Motivo<textarea name="reason"></textarea></label>
        <div class="full row-actions">
          <button class="btn btn-primary" type="submit">Guardar cita</button>
          <button class="btn btn-ghost" type="button" id="closeModalBtn">Cancelar</button>
        </div>
      </form>
    `);
    document.getElementById("closeModalBtn").onclick = closeModal;
    document.getElementById("apptForm").onsubmit = async (ev) => {
      ev.preventDefault();
      const body = Object.fromEntries(new FormData(ev.target).entries());
      body.starts_at = new Date(body.starts_at).toISOString();
      await api("/api/appointments", { method: "POST", body: JSON.stringify(body) });
      toast("Cita agendada");
      closeModal();
      loadDashboard();
    };
  });

  document.getElementById("newSupplierBtn").onclick = async () => {
    openModal(`
      <h2>Nuevo proveedor</h2>
      <form id="supForm" class="form-grid">
        <label>Nombre<input name="name" required /></label>
        <label>Ciudad<input name="city" value="Liberia" /></label>
        <label>Teléfono<input name="phone" /></label>
        <label>Email<input name="email" /></label>
        <label class="full">Notas<textarea name="notes"></textarea></label>
        <div class="full row-actions">
          <button class="btn btn-primary" type="submit">Guardar</button>
          <button class="btn btn-ghost" type="button" id="closeModalBtn">Cancelar</button>
        </div>
      </form>
    `);
    document.getElementById("closeModalBtn").onclick = closeModal;
    document.getElementById("supForm").onsubmit = async (ev) => {
      ev.preventDefault();
      const body = Object.fromEntries(new FormData(ev.target).entries());
      await api("/api/suppliers", { method: "POST", body: JSON.stringify(body) });
      toast("Proveedor agregado");
      closeModal();
      loadSuppliers();
    };
  };

  initZones();
  loadSettings();
  showSection("tablero");
}

bindUI();
