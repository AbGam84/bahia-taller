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

const STATUS_FLOW = [
  "recibido",
  "en_diagnostico",
  "esperando_repuestos",
  "en_reparacion",
  "listo",
  "entregado",
];

const STATUS_LABELS = {
  recibido: "Recibido",
  en_diagnostico: "En diagnóstico",
  esperando_repuestos: "Esperando repuestos",
  en_reparacion: "En reparación",
  listo: "Listo",
  entregado: "Entregado",
};

function nextPatioStatus(current) {
  const i = STATUS_FLOW.indexOf(current);
  if (i < 0 || i >= STATUS_FLOW.length - 1) return null;
  return STATUS_FLOW[i + 1];
}

function avanceControlsHtml(currentStatus) {
  const next = nextPatioStatus(currentStatus);
  const buttons = [
    ["en_diagnostico", "Diagnóstico", "btn-ghost"],
    ["esperando_repuestos", "Esperando pieza", "btn-ghost"],
    ["en_reparacion", "En reparación", "btn-warn"],
    ["listo", "Listo", "btn-ok"],
    ["entregado", "Entregar", "btn-primary"],
  ]
    .filter(([st]) => st !== currentStatus)
    .map(
      ([st, label, cls]) =>
        `<button type="button" class="btn ${cls} btn-avance" data-status="${st}">${label}</button>`
    )
    .join("");
  return `
    <div class="avance-box" style="margin-top:14px;padding:12px;border:1px solid var(--line);border-radius:14px;background:rgba(0,0,0,0.18)">
      <h3 style="margin:0 0 6px">Avance del patio</h3>
      <p class="muted" style="margin:0 0 10px">Ahora: ${badge(currentStatus)}${
        next
          ? ` · Siguiente: <strong>${STATUS_LABELS[next] || next}</strong>`
          : " · Ya entregado"
      }</p>
      <div class="row-actions">
        ${
          next
            ? `<button type="button" class="btn btn-primary" id="btnAvanceNext" data-status="${next}">Avanzar a ${STATUS_LABELS[next] || next}</button>`
            : ""
        }
        ${buttons}
      </div>
    </div>`;
}

const BRAND = "Katire";
const arrivalPhotoFiles = [];
let signaturePad = null;
let tallerActiveId = null;

const money = (n) =>
  new Intl.NumberFormat("es-CR", { style: "currency", currency: "CRC", maximumFractionDigits: 0 }).format(n || 0);

const esc = (s) =>
  String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

const toast = (msg) => {
  const el = document.getElementById("toast");
  if (!el) {
    console.warn(msg);
    return;
  }
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 3500);
};

const setHtml = (id, html) => {
  const el = document.getElementById(id);
  if (el) el.innerHTML = html;
  return el;
};
const setText = (id, text) => {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
  return el;
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
  const run = async (fn) => {
    try {
      await fn();
    } catch (err) {
      toast(err.message || "Error al cargar la sección");
    }
  };
  if (name === "tablero") run(loadDashboard);
  if (name === "recepcion") {
    run(loadReceptions);
    // Firma: redimensionar cuando la sección ya es visible (si no, el canvas queda a 0px)
    requestAnimationFrame(() => resizeSignaturePad(true));
  }
  if (name === "taller") run(loadTaller);
  if (name === "bodega") {
    run(loadParts);
    setTimeout(() => document.getElementById("barcodeScan")?.focus(), 60);
  }
  if (name === "proveedores") run(loadSuppliers);
  if (name === "aliados") run(loadAliados);
  if (name === "config") run(loadSettings);
  if (name === "facturacion") run(loadFacturacion);
}

async function loadFeReadiness() {
  const box = document.getElementById("feReadyBody");
  if (!box) return;
  try {
    const r = await api("/api/fe/readiness");
    const labels = {
      emisor_nombre: "Nombre + cédula emisor",
      actividad: "Código actividad económica",
      atv_user: "Usuario ATV",
      atv_password: "Clave ATV",
      cert_p12: "Certificado .p12",
      cert_pin: "PIN del .p12",
    };
    const items = Object.entries(r.checks || {})
      .map(([k, ok]) => `<span class="badge ${ok ? "badge-ok" : "badge-low"}">${ok ? "OK" : "Falta"} · ${labels[k] || k}</span>`)
      .join(" ");
    box.innerHTML = `
      <p style="margin:0 0 10px"><strong>${r.ready ? "Listo para transmitir" : "Configuración incompleta"}</strong>
      · Ambiente: ${esc(r.ambiente || "")}</p>
      <div class="row-actions">${items}</div>
      <p class="muted" style="margin:10px 0 0">${esc(r.message || "")}</p>`;
  } catch (err) {
    box.textContent = err.message || "No se pudo verificar";
  }
}

async function loadFacturacion() {
  let issuer = {};
  try {
    issuer = await api("/api/fe/issuer");
  } catch (err) {
    toast(err.message || "No se pudo cargar emisor FE");
  }
  const form = document.getElementById("issuerForm");
  if (form && issuer) {
    Object.keys(issuer).forEach((k) => {
      if (
        form[k] !== undefined &&
        !["hacienda_password", "pin_cert", "has_password", "has_cert", "has_pin", "id", "cert_filename"].includes(k)
      ) {
        form[k].value = issuer[k] ?? "";
      }
    });
  }
  const certStatus = document.getElementById("certStatus");
  if (certStatus) {
    certStatus.textContent = issuer.has_cert
      ? `Certificado cargado: ${issuer.cert_filename || "sí"} · PIN ${issuer.has_pin ? "guardado" : "pendiente"}`
      : "Sin certificado cargado — complete ATV y .p12 para transmitir";
  }
  await loadFeReadiness();
  let rows = [];
  try {
    rows = await api("/api/fe/invoices");
  } catch (err) {
    setHtml("feBody", `<tr><td colspan="5" class="muted">${esc(err.message || "Sin acceso a comprobantes")}</td></tr>`);
    return;
  }
  setHtml(
    "feBody",
    rows
      .map(
        (inv) => `<tr>
      <td><code style="font-size:0.72rem">${esc(inv.clave)}</code><br><span class="muted">${esc(inv.numero_consecutivo)}</span></td>
      <td>${esc(inv.tipo_documento)}</td>
      <td class="money">${money(inv.total_comprobante)}</td>
      <td>${badge(inv.status)}<br><span class="muted">${esc(inv.hacienda_status || "")}</span></td>
      <td class="row-actions">
        <button class="btn btn-ghost" data-xml="${inv.id}">XML</button>
        <button class="btn btn-ghost" data-print="${inv.id}">PDF</button>
        <button class="btn btn-ok" data-send="${inv.id}">Enviar MH</button>
        <button class="btn btn-ghost" data-refresh="${inv.id}">Estado</button>
        <button class="btn btn-primary" data-sinpe-inv="${inv.id}">Cierre colones</button>
      </td>
    </tr>`
      )
      .join("") ||
      `<tr><td colspan="5"><div class="empty-state"><strong>Sin comprobantes</strong>Emita desde una OT y envíe a Hacienda</div></td></tr>`
  );

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
        toast("Firmando y enviando a Hacienda…");
        const res = await api(`/api/fe/invoices/${btn.dataset.send}/send`, { method: "POST", body: "{}" });
        toast(res.message || (res.ok ? "Aceptado por Hacienda" : "Revise firma / ATV"));
        loadFacturacion();
      } catch (err) {
        toast(err.message);
      }
    };
  });
  document.querySelectorAll("[data-refresh]").forEach((btn) => {
    btn.onclick = async () => {
      try {
        const res = await api(`/api/fe/invoices/${btn.dataset.refresh}/refresh-status`, {
          method: "POST",
          body: "{}",
        });
        toast(res.message || res.ind_estado || "Estado actualizado");
        loadFacturacion();
      } catch (err) {
        toast(err.message);
      }
    };
  });
  document.querySelectorAll("[data-sinpe-inv]").forEach((btn) => {
    btn.onclick = () => openSinpeCobro({ invoice_id: Number(btn.dataset.sinpeInv) });
  });
}

async function openSinpeCobro({ work_order_id, invoice_id } = {}) {
  try {
    const res = await api("/api/payments/sinpe-link", {
      method: "POST",
      body: JSON.stringify({ work_order_id, invoice_id, mark_sent: true }),
    });
    const q = work_order_id
      ? `work_order_id=${work_order_id}`
      : `invoice_id=${invoice_id}`;
    openModal(`
      <h2>Cierre en colones</h2>
      <p class="muted"><strong>Con prueba.</strong> WhatsApp al cliente + comprobante imprimible (SINPE + referencia + FE).</p>
      <p><strong>${esc(res.reference)}</strong> · ${money(res.amount)} · ${badge(res.payment_status || "sinpe_enviado")}</p>
      <p class="muted">SINPE: ${esc(res.sinpe_phone)} · ${esc(res.sinpe_name)}</p>
      ${res.fe_clave ? `<p class="muted">FE: <code>${esc(res.fe_clave)}</code></p>` : `<p class="muted">FE: pendiente de emitir</p>`}
      <div class="row-actions" style="margin-top:12px">
        ${res.wa_url ? `<a class="btn btn-ok" href="${esc(res.wa_url)}" target="_blank" rel="noopener">WhatsApp cobro</a>` : ""}
        <button class="btn btn-primary" type="button" id="printCierre">Imprimir prueba</button>
        <button class="btn btn-ghost" type="button" id="copySinpeMsg">Copiar mensaje</button>
        <button class="btn btn-ghost" type="button" id="closeModalBtn">Cerrar</button>
      </div>
    `);
    document.getElementById("closeModalBtn").onclick = closeModal;
    document.getElementById("copySinpeMsg").onclick = async () => {
      await navigator.clipboard.writeText(res.message);
      toast("Mensaje copiado");
    };
    document.getElementById("printCierre").onclick = async () => {
      const r = await fetch(`/api/payments/cierre-proof?${q}`, {
        headers: { Authorization: `Bearer ${token()}` },
      });
      const html = await r.text();
      if (!r.ok) {
        toast("No se pudo abrir la prueba");
        return;
      }
      const w = window.open("", "_blank");
      w.document.write(html);
      w.document.close();
    };
    if (res.wa_url) toast(`Cierre ${res.reference} · ${money(res.amount)}`);
  } catch (err) {
    toast(err.message || "No se pudo generar cobro SINPE");
  }
}

function openModal(html) {
  const body = document.getElementById("modalBody");
  const modal = document.getElementById("modal");
  if (!body || !modal) return;
  body.innerHTML = html;
  modal.classList.add("show");
}
function closeModal() {
  const body = document.getElementById("modalBody");
  const modal = document.getElementById("modal");
  if (modal) modal.classList.remove("show");
  if (body) body.innerHTML = "";
}

const VEHICLE_MODELS = {
  Toyota: ["Corolla", "Yaris", "Hilux", "Rav4", "Fortuner", "Prado", "Rush", "Agya", "Otro"],
  Nissan: ["Versa", "Sentra", "Frontier", "X-Trail", "March", "Navara", "Otro"],
  Hyundai: ["Accent", "Tucson", "Santa Fe", "Elantra", "Creta", "i10", "Otro"],
  Kia: ["Rio", "Sportage", "Sorento", "Picanto", "Seltos", "Otro"],
  Suzuki: ["Swift", "Vitara", "Jimny", "Alto", "Dzire", "Otro"],
  Honda: ["Civic", "CR-V", "Fit", "HR-V", "City", "Otro"],
  Mazda: ["Mazda3", "CX-5", "CX-30", "BT-50", "Otro"],
  Mitsubishi: ["L200", "Montero", "Outlander", "ASX", "Otro"],
  Chevrolet: ["Spark", "Aveo", "Sail", "Colorado", "Tracker", "Otro"],
  Ford: ["Ranger", "Escape", "Explorer", "Fiesta", "Otro"],
  Volkswagen: ["Jetta", "Gol", "Tiguan", "Polo", "Otro"],
  Isuzu: ["D-Max", "mu-X", "Otro"],
  "Great Wall": ["Wingle", "Poer", "Otro"],
  BYD: ["Yuan", "Song", "Dolphin", "Otro"],
  Otra: ["Otro"],
};

function initZones() {
  const grid = document.getElementById("zoneGrid");
  if (!grid) return;
  if (grid.dataset.bound === "1") return;
  grid.dataset.bound = "1";
  grid.innerHTML = ZONES.map(
    (z) => `<button type="button" class="zone-chip" data-zone="${z}">${z}</button>`
  ).join("");
  grid.addEventListener("click", (e) => {
    const btn = e.target.closest(".zone-chip");
    if (btn) btn.classList.toggle("active");
  });
}

function initIntakeVehicleOptions() {
  const brand = document.getElementById("intakeBrand");
  const model = document.getElementById("intakeModel");
  const modelOther = document.getElementById("intakeModelOther");
  const year = document.getElementById("intakeYear");
  if (!brand || !model || brand.dataset.bound === "1") return;
  brand.dataset.bound = "1";

  if (year && year.options.length <= 1) {
    const yNow = new Date().getFullYear() + 1;
    for (let y = yNow; y >= 1990; y -= 1) {
      const opt = document.createElement("option");
      opt.value = String(y);
      opt.textContent = String(y);
      year.appendChild(opt);
    }
  }

  const fillModels = () => {
    const list = VEHICLE_MODELS[brand.value] || ["Otro"];
    model.innerHTML = `<option value="">Seleccione modelo…</option>${list
      .map((m) => `<option value="${m}">${m}</option>`)
      .join("")}`;
    if (modelOther) {
      modelOther.style.display = "none";
      modelOther.required = false;
      modelOther.value = "";
    }
  };

  brand.addEventListener("change", fillModels);
  model.addEventListener("change", () => {
    if (!modelOther) return;
    const needsOther = model.value === "Otro" || brand.value === "Otra";
    modelOther.style.display = needsOther ? "block" : "none";
    modelOther.required = needsOther;
    if (!needsOther) modelOther.value = "";
  });
}

function renderPhotoPreviews() {
  const grid = document.getElementById("photoPreviewGrid");
  if (!grid) return;
  if (!arrivalPhotoFiles.length) {
    grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1;padding:18px"><strong>Sin fotos aún</strong>Agregue al menos una del estado del vehículo</div>`;
    return;
  }
  grid.innerHTML = arrivalPhotoFiles
    .map(
      (file, i) => `<figure>
        <img src="${URL.createObjectURL(file)}" alt="Foto ${i + 1}" />
        <button type="button" data-rm="${i}" aria-label="Quitar">×</button>
      </figure>`
    )
    .join("");
  grid.querySelectorAll("[data-rm]").forEach((btn) => {
    btn.onclick = () => {
      arrivalPhotoFiles.splice(Number(btn.dataset.rm), 1);
      renderPhotoPreviews();
    };
  });
}

function isLikelyImageFile(file) {
  if (!file) return false;
  if (file.type && file.type.startsWith("image/")) return true;
  const name = String(file.name || "").toLowerCase();
  return /\.(jpe?g|png|webp|heic|heif)$/i.test(name);
}

function initArrivalPhotos() {
  const input = document.getElementById("arrivalPhotos");
  const clearBtn = document.getElementById("clearPhotosBtn");
  if (!input || input.dataset.bound === "1") return;
  input.dataset.bound = "1";
  input.addEventListener("change", () => {
    let skipped = 0;
    [...(input.files || [])].forEach((f) => {
      if (isLikelyImageFile(f)) arrivalPhotoFiles.push(f);
      else skipped += 1;
    });
    input.value = "";
    renderPhotoPreviews();
    if (skipped) toast(`${skipped} archivo(s) no eran imagen y se omitieron`);
  });
  clearBtn?.addEventListener("click", () => {
    arrivalPhotoFiles.length = 0;
    renderPhotoPreviews();
  });
  renderPhotoPreviews();
}

function resizeSignaturePad(keepDrawing = false) {
  const canvas = document.getElementById("signaturePad");
  if (!canvas || !signaturePad?.ctx) return;
  const prev = keepDrawing && signaturePad.isDirty() ? canvas.toDataURL("image/png") : null;
  const ctx = signaturePad.ctx;
  const ratio = Math.max(window.devicePixelRatio || 1, 1);
  const rect = canvas.getBoundingClientRect();
  const cssW = Math.max(Math.floor(rect.width || canvas.clientWidth || 0), 280);
  const cssH = 180;
  canvas.width = Math.floor(cssW * ratio);
  canvas.height = Math.floor(cssH * ratio);
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.scale(ratio, ratio);
  ctx.fillStyle = "#f7f1ea";
  ctx.fillRect(0, 0, cssW, cssH);
  ctx.strokeStyle = "#1a1410";
  ctx.lineWidth = 2.2;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  signaturePad.cssW = cssW;
  signaturePad.cssH = cssH;
  if (prev) {
    const img = new Image();
    img.onload = () => {
      ctx.drawImage(img, 0, 0, cssW, cssH);
      signaturePad._dirty = true;
    };
    img.src = prev;
  } else {
    signaturePad._dirty = false;
  }
}

function initSignaturePad() {
  const canvas = document.getElementById("signaturePad");
  if (!canvas || canvas.dataset.bound === "1") return;
  canvas.dataset.bound = "1";
  const ctx = canvas.getContext("2d");
  let drawing = false;
  let dirty = false;

  signaturePad = {
    ctx,
    cssW: 640,
    cssH: 180,
    get _dirty() {
      return dirty;
    },
    set _dirty(v) {
      dirty = !!v;
    },
    isDirty: () => dirty,
    toBlob: () =>
      new Promise((resolve) => {
        canvas.toBlob((blob) => resolve(blob), "image/png");
      }),
    clear: () => {
      const w = signaturePad.cssW || 640;
      const h = signaturePad.cssH || 180;
      ctx.fillStyle = "#f7f1ea";
      ctx.fillRect(0, 0, w, h);
      dirty = false;
    },
  };

  const pos = (e) => {
    const rect = canvas.getBoundingClientRect();
    const src = e.touches ? e.touches[0] : e;
    const scaleX = (signaturePad.cssW || rect.width) / (rect.width || 1);
    const scaleY = (signaturePad.cssH || rect.height) / (rect.height || 1);
    return {
      x: (src.clientX - rect.left) * scaleX,
      y: (src.clientY - rect.top) * scaleY,
    };
  };
  const start = (e) => {
    e.preventDefault();
    drawing = true;
    const p = pos(e);
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
  };
  const move = (e) => {
    if (!drawing) return;
    e.preventDefault();
    const p = pos(e);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    dirty = true;
  };
  const end = () => {
    drawing = false;
  };
  canvas.addEventListener("mousedown", start);
  canvas.addEventListener("mousemove", move);
  window.addEventListener("mouseup", end);
  canvas.addEventListener("touchstart", start, { passive: false });
  canvas.addEventListener("touchmove", move, { passive: false });
  canvas.addEventListener("touchend", end);
  document.getElementById("clearSigBtn")?.addEventListener("click", () => signaturePad.clear());
  window.addEventListener("resize", () => {
    if (document.getElementById("sec-recepcion")?.classList.contains("active")) {
      resizeSignaturePad(true);
    }
  });
  resizeSignaturePad(false);
}

async function uploadArrivalMedia(receptionId) {
  const errors = [];
  for (const file of arrivalPhotoFiles) {
    try {
      const fd = new FormData();
      fd.append("file", file, file.name || "foto.jpg");
      fd.append("zone", "Ingreso");
      fd.append("caption", "Foto al llegar");
      await api(`/api/receptions/${receptionId}/photos`, { method: "POST", body: fd, headers: {} });
    } catch (err) {
      errors.push(err.message || "foto");
    }
  }
  if (signaturePad?.isDirty()) {
    try {
      const blob = await signaturePad.toBlob();
      if (blob) {
        const fd = new FormData();
        fd.append("file", blob, "firma.png");
        fd.append("zone", "Firma");
        fd.append("caption", "Firma de quien entrega");
        await api(`/api/receptions/${receptionId}/photos`, { method: "POST", body: fd, headers: {} });
      }
    } catch (err) {
      errors.push(err.message || "firma");
    }
  }
  return errors;
}

async function loadSettings() {
  const s = await api("/api/settings");
  setText("shopSlogan", s.slogan || "De la llave al XML.");
  // Negocio: Autorespuesto (no Aitorepuestos)
  let shopName = String(s.shop_name || "Autorespuesto");
  shopName = shopName.replace(/aitorepuestos?/gi, "Autorespuesto");
  if (!/autorespuesto/i.test(shopName)) shopName = "Autorespuesto";
  setText("shopNameLabel", shopName);
  const form = document.getElementById("settingsForm");
  if (!form) return;
  if (form.shop_name) form.shop_name.value = s.shop_name || "Autorespuesto";
  if (form.slogan) form.slogan.value = s.slogan || "De la llave al XML.";
  if (form.phone) form.phone.value = s.phone || "+506 8870-8123";
  if (form.whatsapp) form.whatsapp.value = s.whatsapp || "+506 8870-8123";
  if (form.address) form.address.value = s.address || "Costa Rica";
  if (form.labor_rate) form.labor_rate.value = s.labor_rate || 15000;
  if (form.sinpe_phone) form.sinpe_phone.value = s.sinpe_phone || s.whatsapp || "";
  if (form.sinpe_name) form.sinpe_name.value = s.sinpe_name || s.shop_name || "";

  try {
    const users = await api("/api/users");
    setHtml(
      "usersBody",
      users
        .map((u) => `<tr><td>${u.name}</td><td>${u.username}</td><td>${u.role}</td></tr>`)
        .join("") || `<tr><td colspan="3" class="muted">Sin usuarios adicionales</td></tr>`
    );
  } catch (_) {
    setHtml("usersBody", `<tr><td colspan="3" class="muted">Solo el administrador ve el equipo</td></tr>`);
  }

  const services = await api("/api/services");
  setHtml(
    "servicesBody",
    services
      .map((s) => `<tr><td>${s.name}</td><td>${s.category}</td><td>${s.hours}</td><td class="money">${money(s.price)}</td></tr>`)
      .join("") ||
      `<tr><td colspan="4"><div class="empty-state"><strong>Planilla vacía</strong>Agregue los servicios reales de su taller</div></td></tr>`
  );
}

function paintUser(u) {
  if (!u) return;
  try {
    localStorage.setItem("tp_user", JSON.stringify(u));
  } catch (_) {}
  const name = u.name || u.username || "Usuario";
  const role = u.role || "";
  setText("userName", name);
  setText("userRole", role);
}

async function loadDashboard() {
  try {
    let d = await api("/api/dashboard");
    // Patio vacío = no sirve al cliente: sembrar / reabrir carro abierto
    if (Number(d.in_shop || 0) === 0 || !(d.board || []).length) {
      try {
        await api("/api/bootstrap/workspace", { method: "POST", body: "{}" });
        d = await api("/api/dashboard");
      } catch (_) {}
    }

    setHtml(
      "metricsPro",
      `
      <div class="metric-card"><div class="k">Ingreso hoy</div><div class="v">${money(d.revenue_today)}</div><div class="s">Órdenes cerradas del día</div></div>
      <div class="metric-card"><div class="k">ARO</div><div class="v">${money(d.aro)}</div><div class="s">Ticket promedio</div></div>
      <div class="metric-card"><div class="k">Conversión cotización</div><div class="v">${d.estimate_conversion_pct || 0}%</div><div class="s">${d.estimate_approved || 0} aprobadas / ${d.estimate_declined || 0} rechazadas</div></div>
      <div class="metric-card"><div class="k">Margen repuestos</div><div class="v">${d.parts_margin_pct || 0}%</div><div class="s">${money(d.parts_margin)} esta temporada</div></div>
    `
    );
    setHtml(
      "stats",
      `
      <div class="stat"><div class="label">Entraron hoy</div><div class="value">${d.today_receptions}</div></div>
      <div class="stat"><div class="label">En el patio</div><div class="value">${d.in_shop}</div></div>
      <div class="stat"><div class="label">Listos</div><div class="value">${d.ready_for_delivery}</div></div>
      <div class="stat"><div class="label">Piezas en ruta</div><div class="value">${d.open_purchase_orders}</div></div>
      <div class="stat"><div class="label">Bajo mínimo</div><div class="value">${d.low_stock_count}</div></div>
    `
    );
    const kanban = document.getElementById("kanban");
    if (kanban) {
      const board = d.board || [];
      if (!board.length) {
        kanban.innerHTML = `<div class="empty-state"><strong>Patio libre</strong>
          Pulse «+ Recibir vehículo» para el primer ingreso real.
          <div class="row-actions" style="margin-top:12px;justify-content:center">
            <button type="button" class="btn btn-primary" data-go="recepcion">Ir a Ingreso</button>
          </div></div>`;
        kanban.querySelector("[data-go]")?.addEventListener("click", () => showSection("recepcion"));
      } else {
        kanban.innerHTML = STATUS_COLS.map(([key, title]) => {
          const list = board.filter((r) => r.status === key);
          const cards =
            list
              .map((r) => {
                const v = r.vehicle || {};
                return `<div class="card-job" data-id="${r.id}" role="button" tabindex="0">
              <strong>${esc(v.plate || "—")}</strong>
              <div class="meta">${esc(v.brand || "")} ${esc(v.model || "")}<br>${esc(r.code)}<br>${esc((r.customer_complaint || "").slice(0, 60))}</div>
            </div>`;
              })
              .join("") ||
            `<div class="muted" style="padding:10px;font-size:0.82rem">Sin carros</div>`;
          return `<div class="kanban-col"><h4>${title}<span>${list.length}</span></h4>${cards}</div>`;
        }).join("");
        kanban.querySelectorAll(".card-job").forEach((el) => {
          el.addEventListener("click", () => openReception(Number(el.dataset.id)));
        });
      }
    }
    setHtml(
      "lowStockBody",
      (d.low_stock || [])
        .map(
          (p) => `<tr>
        <td>${p.sku}</td><td>${p.name}</td>
        <td><span class="badge badge-low">${p.stock_qty}</span></td>
        <td>${p.min_stock}</td><td>${p.preferred_supplier || "—"}</td>
      </tr>`
        )
        .join("") ||
        `<tr><td colspan="5"><div class="empty-state"><strong>Estantería firme</strong>Nada bajo el mínimo ahora</div></td></tr>`
    );

    setHtml(
      "apptBody",
      (d.appointments || [])
        .map(
          (a) => `<tr>
        <td>${new Date(a.starts_at).toLocaleString("es-CR")}</td>
        <td>${a.customer_name}<br><span class="muted">${a.phone || ""}</span></td>
        <td>${a.plate} ${a.vehicle_info || ""}</td>
        <td>${a.reason || "—"}</td>
        <td>${badge(a.status)}</td>
      </tr>`
        )
        .join("") ||
        `<tr><td colspan="5"><div class="empty-state"><strong>Sin citas</strong>Planilla lista — agende la primera</div></td></tr>`
    );
  } catch (err) {
    toast(err.message || "No se pudo cargar el patio");
  }
}

async function loadReceptions() {
  const rows = await api("/api/receptions");
  setHtml(
    "receptionList",
    rows
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
      .join("") ||
      `<tr><td colspan="4"><div class="empty-state"><strong>Sin ingresos</strong>Planilla lista para el primer vehículo</div></td></tr>`
  );
  document.querySelectorAll("#receptionList [data-id]").forEach((btn) => {
    btn.addEventListener("click", () => openReception(Number(btn.dataset.id)));
  });
}

async function loadTaller() {
  const list = document.getElementById("tallerList");
  if (!list) return;
  try {
    const rows = await api("/api/receptions");
    const open = rows.filter((r) => r.status !== "entregado" && r.status !== "cancelado");
    if (!open.length) {
      list.innerHTML = `<div class="empty-state"><strong>Patio libre</strong>Haga un ingreso primero (fotos + daños + firma)</div>
        <button class="btn btn-primary" data-go="recepcion" style="width:100%;margin-top:10px">Ir a Ingreso</button>`;
      list.querySelector("[data-go]")?.addEventListener("click", () => showSection("recepcion"));
      if (!tallerActiveId) {
        document.getElementById("tallerWorkspace").innerHTML =
          `<div class="empty-state"><strong>Sin vehículos</strong>Cuando entre un carro, aquí hará la lectura y la OT.</div>`;
      }
      return;
    }
    list.innerHTML = open
      .map((r) => {
        const v = r.vehicle || {};
        const c = v.customer || {};
        const active = Number(r.id) === Number(tallerActiveId) ? "active" : "";
        return `<button type="button" class="taller-card ${active}" data-id="${r.id}">
          <strong>${esc(v.plate || "—")}</strong>
          <div class="meta">${esc(v.brand)} ${esc(v.model)} · ${esc(c.name || "")}<br>${esc(r.code)} · ${badge(r.status)} · OT ${esc(r.work_order?.code || "—")}</div>
        </button>`;
      })
      .join("");
    list.querySelectorAll(".taller-card").forEach((btn) => {
      btn.onclick = () => openTallerJob(Number(btn.dataset.id));
    });
    if (tallerActiveId) {
      const still = open.some((r) => r.id === tallerActiveId);
      if (still) await openTallerJob(tallerActiveId);
      else tallerActiveId = null;
    }
  } catch (err) {
    toast(err.message || "No se pudo cargar Diagnóstico & OT");
  }
}

async function openTallerJob(id) {
  tallerActiveId = id;
  const ws = document.getElementById("tallerWorkspace");
  document.querySelectorAll("#tallerList .taller-card").forEach((el) => {
    el.classList.toggle("active", Number(el.dataset.id) === id);
  });
  ws.innerHTML = `<div class="empty-state"><strong>Cargando lectura…</strong></div>`;
  try {
    const r = await api(`/api/receptions/${id}`);
    const v = r.vehicle || {};
    const c = v.customer || {};
    const d = r.diagnosis || {};
    const wo = r.work_order;
    const checks = r.inspection || [];

    ws.innerHTML = `
      <div class="panel-head" style="margin-bottom:12px">
        <div>
          <h2 style="margin:0;font-family:var(--display)">${esc(v.plate)} · ${esc(v.brand)} ${esc(v.model)}</h2>
          <p class="muted" style="margin:6px 0 0">${esc(r.code)} · ${esc(c.name || "")} · ${badge(r.status)}</p>
          <p style="margin:10px 0 0"><strong>Queja:</strong> ${esc(r.customer_complaint || "—")}</p>
        </div>
        <div class="row-actions">
          <button class="btn btn-ghost" id="printDiagBtn">Imprimir diagnóstico</button>
          <button class="btn btn-ghost" id="buyPartsBtn">Buscar repuestos</button>
          <button class="btn btn-ghost" id="sendAllyBtn">Enviar a aliado</button>
        </div>
      </div>

      <h3>1 · Lectura por sistemas (semáforo)</h3>
      <p class="muted" style="margin-top:0">Verde OK · Amarillo vigilar · Rojo falla</p>
      <div class="dvi-grid" id="dviGrid">
        ${checks.map((ch) => `
          <div class="dvi-item" data-key="${esc(ch.system_key)}">
            <div class="name">${esc(ch.system_name)}</div>
            <div class="lights">
              <button type="button" data-st="ok" class="${ch.status === "ok" ? "on-ok" : ""}">OK</button>
              <button type="button" data-st="watch" class="${ch.status === "watch" ? "on-watch" : ""}">!</button>
              <button type="button" data-st="fail" class="${ch.status === "fail" ? "on-fail" : ""}">X</button>
              <button type="button" data-st="na" class="${ch.status === "na" ? "on-na" : ""}">—</button>
            </div>
          </div>`).join("") || `<div class="muted">Sin checklist</div>`}
      </div>
      <div class="row-actions" style="margin-bottom:18px">
        <button class="btn btn-ghost" id="saveDviBtn">Guardar lectura</button>
      </div>

      <h3>2 · Diagnóstico del mecánico</h3>
      <form id="tallerDiagForm" class="form-grid">
        <label>Técnico<input name="technician" value="${esc(d.technician || user()?.name || "")}" required /></label>
        <label>Prioridad
          <select name="priority">
            <option value="normal" ${d.priority === "normal" || !d.priority ? "selected" : ""}>normal</option>
            <option value="alta" ${d.priority === "alta" ? "selected" : ""}>alta</option>
            <option value="urgente" ${d.priority === "urgente" ? "selected" : ""}>urgente</option>
          </select>
        </label>
        <label class="full">Síntomas<textarea name="symptoms" required>${esc(d.symptoms || r.customer_complaint || "")}</textarea></label>
        <label class="full">Hallazgos<textarea name="findings" required placeholder="Qué encontró en el carro">${esc(d.findings || "")}</textarea></label>
        <label class="full">Códigos OBD (opcional)<input name="obd_codes" value="${esc(d.obd_codes || "")}" placeholder="P0301, C1201..." /></label>
        <label class="full">Trabajo recomendado<textarea name="recommended_work" required placeholder="Ej. Cambio de pastillas delanteras + rectificado">${esc(d.recommended_work || "")}</textarea></label>
        <label>Horas estimadas<input name="estimated_hours" type="number" step="0.25" min="0.25" value="${esc(d.estimated_hours || 1)}" required /></label>
        <div class="full row-actions">
          <button class="btn btn-primary" type="submit" id="saveDiagBtn">Guardar diagnóstico y crear OT</button>
        </div>
      </form>

      <div id="tallerOtBox" style="margin-top:18px">
        ${wo ? `
          <h3>3 · Orden de trabajo ${esc(wo.code)}</h3>
          <p class="muted">Mano de obra: ${money(wo.labor_total)} · Repuestos: ${money(wo.parts_total)} · <strong>Total ${money(wo.grand_total)}</strong></p>
          <p>${esc(wo.labor_notes || d.recommended_work || "")}</p>
          <ul>${(wo.lines || []).map((l) => `<li>${esc(l.description)} × ${l.quantity} · ${badge(l.status)} · ${money(l.line_total)}</li>`).join("") || "<li class='muted'>Sin repuestos aún — agréguelos desde Bodega o la ficha</li>"}</ul>
          <div class="row-actions">
            <button class="btn btn-ghost" id="otOpenFicha">Ver ficha completa</button>
          </div>
        ` : `<p class="muted" style="margin-top:14px">Aún no hay OT. Complete el diagnóstico y pulse el botón verde — o avance el estado abajo.</p>`}
        ${avanceControlsHtml(r.status)}
      </div>
    `;

    const dviState = {};
    checks.forEach((ch) => { dviState[ch.system_key] = ch.status || "na"; });
    ws.querySelectorAll(".dvi-item").forEach((item) => {
      const key = item.dataset.key;
      item.querySelectorAll("button[data-st]").forEach((btn) => {
        btn.onclick = () => {
          dviState[key] = btn.dataset.st;
          item.querySelectorAll("button[data-st]").forEach((b) => {
            b.className = "";
            if (b.dataset.st === dviState[key]) b.classList.add(`on-${dviState[key]}`);
          });
        };
      });
    });

    document.getElementById("saveDviBtn").onclick = async () => {
      try {
        await api(`/api/receptions/${id}/inspection`, {
          method: "PUT",
          body: JSON.stringify({
            items: Object.entries(dviState).map(([system_key, status]) => ({ system_key, status, notes: "" })),
          }),
        });
        toast("Lectura por sistemas guardada");
        loadDashboard();
        openTallerJob(id);
      } catch (err) {
        toast(err.message || "No se pudo guardar la lectura");
      }
    };

    document.getElementById("tallerDiagForm").onsubmit = async (ev) => {
      ev.preventDefault();
      const btn = document.getElementById("saveDiagBtn");
      try {
        btn.disabled = true;
        btn.textContent = "Guardando…";
        // Guarda semáforo también
        await api(`/api/receptions/${id}/inspection`, {
          method: "PUT",
          body: JSON.stringify({
            items: Object.entries(dviState).map(([system_key, status]) => ({ system_key, status, notes: "" })),
          }),
        });
        const fd = new FormData(ev.target);
        const body = Object.fromEntries(fd.entries());
        body.estimated_hours = Number(body.estimated_hours || 1);
        body.create_work_order = true;
        const res = await api(`/api/receptions/${id}/diagnosis`, {
          method: "POST",
          body: JSON.stringify(body),
        });
        toast(`Diagnóstico listo · OT ${res.work_order?.code || "creada"}`);
        loadDashboard();
        await loadTaller();
        await openTallerJob(id);
      } catch (err) {
        toast(err.message || "No se pudo crear el diagnóstico / OT");
      } finally {
        btn.disabled = false;
        btn.textContent = "Guardar diagnóstico y crear OT";
      }
    };

    const patch = async (status) => {
      try {
        await api(`/api/receptions/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) });
        toast(`Estado: ${(STATUS_LABELS[status] || status).replaceAll("_", " ")}`);
        loadDashboard();
        await loadTaller();
        await openTallerJob(id);
      } catch (err) {
        toast(err.message);
      }
    };
    document.getElementById("btnAvanceNext")?.addEventListener("click", (ev) => {
      const st = ev.currentTarget.dataset.status;
      if (st) patch(st);
    });
    ws.querySelectorAll(".btn-avance").forEach((btn) => {
      btn.addEventListener("click", () => patch(btn.dataset.status));
    });
    document.getElementById("otOpenFicha")?.addEventListener("click", () => openReception(id));
    document.getElementById("printDiagBtn")?.addEventListener("click", async () => {
      try {
        const res = await fetch(`/api/receptions/${id}/diagnosis/print`, {
          headers: { Authorization: `Bearer ${token()}` },
        });
        if (!res.ok) throw new Error("No se pudo generar la impresión");
        const html = await res.text();
        const w = window.open("", "_blank");
        w.document.write(html);
        w.document.close();
      } catch (err) {
        toast(err.message);
      }
    });
    document.getElementById("buyPartsBtn")?.addEventListener("click", () => {
      const q = [d.recommended_work, v.brand, v.model, v.year].filter(Boolean).join(" ");
      showSection("proveedores");
      const mq = document.getElementById("marketQuery");
      const mv = document.getElementById("marketVehicle");
      if (mq) mq.value = q || "";
      if (mv) mv.value = `${v.plate || ""} ${v.brand || ""} ${v.model || ""}`.trim();
      runMarketSearch();
    });
    document.getElementById("sendAllyBtn")?.addEventListener("click", () => {
      showSection("aliados");
      openNewAllyJob({
        reception_id: id,
        work_order_id: wo?.id || null,
        plate: v.plate || "",
        vehicle_info: `${v.brand || ""} ${v.model || ""} ${v.year || ""}`.trim(),
        description: d.recommended_work || r.customer_complaint || "",
      });
    });
  } catch (err) {
    ws.innerHTML = `<div class="empty-state"><strong>Error</strong>${esc(err.message || "No se pudo abrir la lectura")}</div>`;
    toast(err.message || "Error al abrir diagnóstico");
  }
}

function openNewSupplier(kind) {
  openModal(`
    <h2>${kind === "aliado" ? "Nuevo aliado" : "Nuevo proveedor / tienda"}</h2>
    <form id="supForm" class="form-grid">
      <label>Nombre<input name="name" required placeholder="${kind === "aliado" ? "Ej. Rectificadora del Norte" : "Ej. Repuestos XYZ"}" /></label>
      <label>Tipo
        <select name="kind">
          <option value="tienda" ${kind === "tienda" ? "selected" : ""}>Tienda de repuestos</option>
          <option value="aliado" ${kind === "aliado" ? "selected" : ""}>Aliado (trabajos externos)</option>
        </select>
      </label>
      <label>Ciudad<input name="city" value="Liberia" /></label>
      <label>Teléfono<input name="phone" /></label>
      <label>WhatsApp<input name="whatsapp" placeholder="50688887777" /></label>
      <label>Email<input name="email" /></label>
      <label class="full">Especialidad<input name="specialty" placeholder="Cajas / motores / frenos..." /></label>
      <label class="full">Sitio web<input name="website" placeholder="https://..." /></label>
      <label class="full">URL búsqueda (use {q})<input name="search_url" placeholder="https://tienda.com/?s={q}" /></label>
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
    try {
      const body = Object.fromEntries(new FormData(ev.target).entries());
      await api("/api/suppliers", { method: "POST", body: JSON.stringify(body) });
      toast(body.kind === "aliado" ? "Aliado registrado" : "Proveedor agregado");
      closeModal();
      if (body.kind === "aliado") loadAliados();
      else loadSuppliers();
    } catch (err) {
      toast(err.message);
    }
  };
}

async function openNewAllyJob(prefill = {}) {
  let allies = [];
  try {
    allies = await api("/api/suppliers?kind=aliado");
  } catch (_) {}
  if (!allies.length) {
    toast("Primero registre un aliado (taller de cajas/motores)");
    return;
  }
  openModal(`
    <h2>Enviar trabajo a aliado</h2>
    <form id="allyJobForm" class="form-grid">
      <label>Aliado
        <select name="ally_id" required>
          ${allies.map((a) => `<option value="${a.id}">${esc(a.name)} — ${esc(a.specialty || "")}</option>`).join("")}
        </select>
      </label>
      <label>Tipo de trabajo
        <select name="job_type">
          <option value="caja_cambios">Caja de cambios</option>
          <option value="motor">Motor / rectificación</option>
          <option value="radiador">Radiador</option>
          <option value="electrico">Eléctrico / alternador</option>
          <option value="inyeccion">Inyección</option>
          <option value="carroceria">Carrocería / pintura</option>
          <option value="otro">Otro</option>
        </select>
      </label>
      <label>Placa<input name="plate" value="${esc(prefill.plate || "")}" /></label>
      <label>Vehículo<input name="vehicle_info" value="${esc(prefill.vehicle_info || "")}" /></label>
      <label>Costo estimado<input name="cost_estimated" type="number" value="0" /></label>
      <label>Entrega prometida<input name="due_at" type="date" /></label>
      <label class="full">Qué se envía<textarea name="description" required placeholder="Ej. Caja automática Toyota Yaris — no engata 3ra">${esc(prefill.description || "")}</textarea></label>
      <input type="hidden" name="reception_id" value="${prefill.reception_id || ""}" />
      <input type="hidden" name="work_order_id" value="${prefill.work_order_id || ""}" />
      <div class="full row-actions">
        <button class="btn btn-primary" type="submit">Registrar envío</button>
        <button class="btn btn-ghost" type="button" id="closeModalBtn">Cancelar</button>
      </div>
    </form>
  `);
  document.getElementById("closeModalBtn").onclick = closeModal;
  document.getElementById("allyJobForm").onsubmit = async (ev) => {
    ev.preventDefault();
    try {
      const fd = new FormData(ev.target);
      const body = Object.fromEntries(fd.entries());
      body.ally_id = Number(body.ally_id);
      body.cost_estimated = Number(body.cost_estimated || 0);
      body.reception_id = body.reception_id ? Number(body.reception_id) : null;
      body.work_order_id = body.work_order_id ? Number(body.work_order_id) : null;
      if (body.due_at) body.due_at = `${body.due_at}T12:00:00`;
      else delete body.due_at;
      const job = await api("/api/ally-jobs", { method: "POST", body: JSON.stringify(body) });
      toast(`Seguimiento ${job.code} creado`);
      closeModal();
      loadAliados();
    } catch (err) {
      toast(err.message);
    }
  };
}

async function loadParts(highlightId) {
  try {
    const q = document.getElementById("partSearch")?.value?.trim() || "";
    const low = !!document.getElementById("onlyLow")?.checked;
    let parts = await api(`/api/parts?q=${encodeURIComponent(q)}&low_stock=${low}`);
    if (!parts.length && !q && !low) {
      await api("/api/bootstrap/workspace", { method: "POST", body: "{}" });
      parts = await api(`/api/parts?q=&low_stock=false`);
    }
    const body = document.getElementById("partsBody");
    if (!body) return;
    body.innerHTML = parts
      .map((p) => `<tr class="${highlightId && p.id === highlightId ? "row-hit" : ""}" data-part-id="${p.id}">
      <td><code>${esc(p.barcode || p.sku)}</code></td>
      <td>${esc(p.sku)}</td>
      <td><strong>${esc(p.name)}</strong><br><span class="muted">${esc(p.brand)} · ${esc(p.category)}</span></td>
      <td>${esc(p.location || "—")}</td>
      <td>${p.low_stock ? `<span class="badge badge-low">${p.stock_qty}</span>` : `<span class="badge badge-ok">${p.stock_qty}</span>`}</td>
      <td class="money">${money(p.sale_price)}</td>
      <td>${esc(p.preferred_supplier || "—")}</td>
      <td class="row-actions">
        <button class="btn btn-ghost" data-adjust="${p.id}">Ajuste</button>
      </td>
    </tr>`)
      .join("") ||
      `<tr><td colspan="8"><div class="empty-state"><strong>Estantería vacía</strong>Escanee con la pistola o pulse «Nueva pieza»</div></td></tr>`;
    document.querySelectorAll("[data-adjust]").forEach((btn) => {
      btn.addEventListener("click", () => adjustPart(Number(btn.dataset.adjust)));
    });
    if (highlightId) {
      body.querySelector(`[data-part-id="${highlightId}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  } catch (err) {
    toast(err.message || "No se pudo cargar bodega");
  }
}

function paintScanResult(res) {
  const box = document.getElementById("scanResult");
  if (!box) return;
  if (!res) {
    box.hidden = true;
    box.innerHTML = "";
    return;
  }
  box.hidden = false;
  if (!res.found || !res.part) {
    box.className = "scan-result scan-miss";
    box.innerHTML = `<strong>Sin coincidencia</strong><span>${esc(res.barcode || "")} — cambie a «Alta si no existe» o cree la pieza</span>`;
    return;
  }
  const p = res.part;
  box.className = "scan-result scan-hit";
  box.innerHTML = `<strong>${esc(p.name)}</strong>
    <span>Barras ${esc(p.barcode || "")} · SKU ${esc(p.sku)} · Stock <b>${p.stock_qty}</b> · ${money(p.sale_price)}</span>
    <span class="muted">${esc(res.message || "")}</span>`;
}

async function runBarcodeScan() {
  const input = document.getElementById("barcodeScan");
  const code = (input?.value || "").trim();
  if (!code) {
    toast("Escanee o escriba un código de barras");
    input?.focus();
    return;
  }
  const action = document.getElementById("scanAction")?.value || "add";
  const quantity = Number(document.getElementById("scanQty")?.value || 1) || 1;
  try {
    let res = await api("/api/parts/scan", {
      method: "POST",
      body: JSON.stringify({ barcode: code, action, quantity }),
    });
    if (!res.found && action === "add") {
      const create = confirm(`Código ${code} no está en bodega.\n¿Dar de alta y sumar ${quantity}?`);
      if (!create) {
        paintScanResult(res);
        return;
      }
      openModal(`
        <h2>Alta por pistola</h2>
        <p class="muted">Código <strong>${esc(code)}</strong></p>
        <form id="scanCreateForm" class="form-grid">
          <label class="full">Nombre<input name="name" required placeholder="Nombre de la pieza" /></label>
          <label>Marca<input name="brand" /></label>
          <label>Categoría<input name="category" value="General" /></label>
          <label>Ubicación<input name="location" /></label>
          <label>Costo<input name="cost_price" type="number" value="0" /></label>
          <label>Precio venta<input name="sale_price" type="number" value="0" /></label>
          <div class="full row-actions">
            <button class="btn btn-primary" type="submit">Guardar y sumar stock</button>
            <button class="btn btn-ghost" type="button" id="closeModalBtn">Cancelar</button>
          </div>
        </form>
      `);
      document.getElementById("closeModalBtn").onclick = closeModal;
      document.getElementById("scanCreateForm").onsubmit = async (ev) => {
        ev.preventDefault();
        const fd = Object.fromEntries(new FormData(ev.target).entries());
        res = await api("/api/parts/scan", {
          method: "POST",
          body: JSON.stringify({
            barcode: code,
            action: "create",
            quantity,
            name: fd.name,
            brand: fd.brand || "",
            category: fd.category || "General",
            location: fd.location || "",
            cost_price: Number(fd.cost_price || 0),
            sale_price: Number(fd.sale_price || 0),
          }),
        });
        closeModal();
        paintScanResult(res);
        toast(res.message || "Pieza lista");
        if (input) input.value = "";
        await loadParts(res.part?.id);
        input?.focus();
      };
      return;
    }
    paintScanResult(res);
    toast(res.message || (res.found ? "OK" : "No encontrado"));
    if (input) input.value = "";
    await loadParts(res.part?.id);
    input?.focus();
  } catch (err) {
    toast(err.message || "Error al escanear");
  }
}

function bindBarcodeScanner() {
  const input = document.getElementById("barcodeScan");
  if (!input || input.dataset.bound === "1") return;
  input.dataset.bound = "1";
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      runBarcodeScan();
    }
  });
  document.getElementById("scanGoBtn")?.addEventListener("click", () => runBarcodeScan());
}

async function runMarketSearch() {
  const q = document.getElementById("marketQuery")?.value?.trim() || "";
  const vehicle = document.getElementById("marketVehicle")?.value?.trim() || "";
  const box = document.getElementById("marketShops");
  if (!box) return;
  try {
    const data = await api(`/api/parts/market-search?q=${encodeURIComponent(q)}&vehicle=${encodeURIComponent(vehicle)}`);
    box.innerHTML = (data.shops || [])
      .map((s) => `<div class="shop-card">
        <h3>${esc(s.name)}</h3>
        <div class="spec">${esc(s.specialty || s.notes || s.city || "")}</div>
        <div class="muted" style="font-size:0.8rem;margin-bottom:8px">${esc(s.phone || "")} ${s.whatsapp ? "· WA " + esc(s.whatsapp) : ""}</div>
        <div class="row-actions">
          ${s.search_link ? `<a class="btn btn-primary" href="${esc(s.search_link)}" target="_blank" rel="noopener">Buscar en web</a>` : ""}
          ${s.whatsapp_link ? `<a class="btn btn-ok" href="${esc(s.whatsapp_link)}" target="_blank" rel="noopener">Pedir por WA</a>` : ""}
          ${s.website ? `<a class="btn btn-ghost" href="${esc(s.website)}" target="_blank" rel="noopener">Sitio</a>` : ""}
        </div>
      </div>`)
      .join("") || `<div class="empty-state"><strong>Sin tiendas</strong>Agregue proveedores tipo tienda</div>`;
  } catch (err) {
    toast(err.message || "No se pudo buscar en tiendas");
  }
}

async function loadSuppliers() {
  const [suppliers, orders] = await Promise.all([
    api("/api/suppliers"),
    api("/api/purchase-orders"),
  ]);
  const tiendas = suppliers.filter((s) => (s.kind || "tienda") !== "aliado");
  setHtml(
    "suppliersBody",
    tiendas
      .map(
        (s) => `<tr>
      <td><strong>${esc(s.name)}</strong><br><span class="muted">${esc(s.specialty || "")}</span></td>
      <td>${esc(s.kind || "tienda")}</td>
      <td>${esc(s.city || "")}</td>
      <td>${esc(s.phone || "")}<br><span class="muted">${esc(s.whatsapp || "")}</span></td>
      <td class="row-actions">
        ${s.website ? `<a class="btn btn-ghost" href="${esc(s.website)}" target="_blank" rel="noopener">Web</a>` : "—"}
      </td>
    </tr>`
      )
      .join("") ||
      `<tr><td colspan="5"><div class="empty-state"><strong>Sin proveedores</strong>Agregue Gigante, Guacamaya u otros</div></td></tr>`
  );
  runMarketSearch();
  setHtml(
    "poBody",
    orders
      .map(
        (po) => `<tr>
      <td>${po.code}<br><span class="muted">${(po.lines || []).map((l) => l.part_name).join(", ")}</span></td>
      <td>${po.supplier?.name || ""}</td>
      <td class="money">${money(po.total)}</td>
      <td>${badge(po.status)}</td>
      <td class="row-actions">
        ${po.status !== "recibido" ? `<button class="btn btn-ok" data-receive="${po.id}">Marcar recibido</button>` : "—"}
        ${po.status === "solicitado" ? `<button class="btn btn-warn" data-ship="${po.id}">En camino</button>` : ""}
      </td>
    </tr>`
      )
      .join("") ||
      `<tr><td colspan="5"><div class="empty-state"><strong>Sin pedidos</strong>Se crean solos cuando falte stock en una OT</div></td></tr>`
  );
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

async function loadAliados() {
  try {
    const [allies, jobs] = await Promise.all([
      api("/api/suppliers?kind=aliado"),
      api("/api/ally-jobs"),
    ]);
    setHtml(
      "alliesList",
      allies
        .map(
          (s) => `<div class="shop-card">
        <h3>${esc(s.name)}</h3>
        <div class="spec">${esc(s.specialty || "Trabajos externos")}</div>
        <div class="muted" style="font-size:0.82rem">${esc(s.city || "")} · ${esc(s.phone || "Sin teléfono")}</div>
        ${s.whatsapp ? `<div class="row-actions" style="margin-top:8px"><a class="btn btn-ok" target="_blank" rel="noopener" href="https://wa.me/${esc(String(s.whatsapp).replace(/\D/g, ""))}">WhatsApp</a></div>` : ""}
      </div>`
        )
        .join("") ||
        `<div class="empty-state"><strong>Sin aliados</strong>Registre el taller donde manda cajas o motores</div>`
    );

    setHtml(
      "allyJobsBody",
      jobs
        .map(
          (j) => `<tr>
        <td>${esc(j.code)}</td>
        <td>${esc(j.ally_name)}</td>
        <td>${esc(j.job_type)}</td>
        <td>${esc(j.plate)}<br><span class="muted">${esc(j.vehicle_info || "")}</span></td>
        <td>${badge(j.status)}</td>
        <td class="money">${money(j.cost_final || j.cost_estimated)}</td>
        <td>${j.due_at ? new Date(j.due_at).toLocaleDateString("es-CR") : "—"}</td>
        <td class="row-actions">
          <button class="btn btn-ghost" data-ally-open="${j.id}">Seguimiento</button>
        </td>
      </tr>`
        )
        .join("") ||
        `<tr><td colspan="8"><div class="empty-state"><strong>Sin envíos</strong>Cuando mande una caja o motor, regístrelo aquí</div></td></tr>`
    );

    document.querySelectorAll("[data-ally-open]").forEach((btn) => {
      btn.onclick = () => openAllyJob(Number(btn.dataset.allyOpen), jobs);
    });
  } catch (err) {
    toast(err.message || "No se pudo cargar aliados");
  }
}

function openAllyJob(id, jobs) {
  const j = (jobs || []).find((x) => x.id === id);
  if (!j) return;
  openModal(`
    <div class="panel-head">
      <div>
        <h2 style="margin:0">${esc(j.code)} · ${esc(j.ally_name)}</h2>
        <p class="muted">${esc(j.job_type)} · ${esc(j.plate)} · ${badge(j.status)}</p>
      </div>
      <button class="btn btn-ghost" id="closeModalBtn">Cerrar</button>
    </div>
    <p>${esc(j.description || "")}</p>
    <p class="muted">Estimado ${money(j.cost_estimated)} · Final ${money(j.cost_final)}</p>
    <h3>Línea de tiempo</h3>
    <ul>${(j.events || []).map((e) => `<li><strong>${esc(e.status)}</strong> — ${esc(e.note)} <span class="muted">(${e.created_at ? new Date(e.created_at).toLocaleString("es-CR") : ""})</span></li>`).join("") || "<li class='muted'>Sin eventos</li>"}</ul>
    <form id="allyTrackForm" class="form-grid" style="margin-top:14px">
      <label>Estado
        <select name="status">
          ${["cotizado", "enviado", "en_proceso", "listo", "recibido", "cancelado"].map((s) => `<option value="${s}" ${j.status === s ? "selected" : ""}>${s}</option>`).join("")}
        </select>
      </label>
      <label>Costo final<input name="cost_final" type="number" value="${j.cost_final || j.cost_estimated || 0}" /></label>
      <label class="full">Nota de seguimiento<textarea name="note" placeholder="Ej. Ya lo recibieron / falta empaque / listo para recoger"></textarea></label>
      <div class="full row-actions">
        <button class="btn btn-primary" type="submit">Guardar seguimiento</button>
      </div>
    </form>
  `);
  document.getElementById("closeModalBtn").onclick = closeModal;
  document.getElementById("allyTrackForm").onsubmit = async (ev) => {
    ev.preventDefault();
    try {
      const fd = new FormData(ev.target);
      const body = {
        status: fd.get("status"),
        note: fd.get("note") || "",
        cost_final: Number(fd.get("cost_final") || 0),
      };
      await api(`/api/ally-jobs/${id}`, { method: "PATCH", body: JSON.stringify(body) });
      toast("Seguimiento actualizado");
      closeModal();
      loadAliados();
    } catch (err) {
      toast(err.message);
    }
  };
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
          <p>${esc(r.customer_complaint || "—")}</p>
          <p class="muted">Combustible: ${esc(r.fuel_level)} · Km: ${esc(r.odometer_km)} · Firma: ${esc(r.customer_signature_name || "—")}</p>
          <button class="btn btn-primary" id="goTallerFromFicha" style="margin-top:10px">Abrir Lectura / OT</button>
        </div>
        <div class="panel" style="box-shadow:none;border:1px solid var(--line)">
          <h3>Daños al llegar</h3>
          ${(r.damages || []).map((x) => `<div style="margin-bottom:8px"><strong>${esc(x.zone)}</strong> · ${esc(x.severity)}<br><span class="muted">${esc(x.description || "")}</span></div>`).join("") || "<p class='muted'>Sin daños registrados</p>"}
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
            <input type="file" name="file" accept="image/*" capture="environment" required />
            <input name="zone" placeholder="Zona" style="max-width:140px" />
            <button class="btn btn-primary" type="submit">Subir foto</button>
          </form>
        </div>
      </div>

      <div>
        <div class="panel" style="box-shadow:none;border:1px solid var(--line)">
          <h3>Diagnóstico guiado</h3>
          <form id="diagForm" class="stack">
            <label>Técnico<input name="technician" value="${esc(d.technician || user()?.name || "")}" /></label>
            <label>Síntomas<textarea name="symptoms">${esc(d.symptoms || r.customer_complaint || "")}</textarea></label>
            <label>Hallazgos del mecánico<textarea name="findings">${esc(d.findings || "")}</textarea></label>
            <label>Códigos OBD (opcional)<input name="obd_codes" value="${esc(d.obd_codes || "")}" placeholder="P0301, C1201..." /></label>
            <label>Trabajo recomendado<textarea name="recommended_work">${esc(d.recommended_work || "")}</textarea></label>
            <div class="form-grid">
              <label>Horas estimadas<input name="estimated_hours" type="number" step="0.5" value="${esc(d.estimated_hours || 1)}" /></label>
              <label>Prioridad
                <select name="priority">
                  <option value="normal" ${!d.priority || d.priority === "normal" ? "selected" : ""}>normal</option>
                  <option value="alta" ${d.priority === "alta" ? "selected" : ""}>alta</option>
                  <option value="urgente" ${d.priority === "urgente" ? "selected" : ""}>urgente</option>
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
  document.getElementById("goTallerFromFicha")?.addEventListener("click", () => {
    closeModal();
    showSection("taller");
    openTallerJob(id);
  });

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
    try {
      const fd = new FormData(e.target);
      const body = Object.fromEntries(fd.entries());
      body.estimated_hours = Number(body.estimated_hours || 1);
      body.create_work_order = true;
      const res = await api(`/api/receptions/${id}/diagnosis`, { method: "POST", body: JSON.stringify(body) });
      toast(`Diagnóstico guardado · OT ${res.work_order?.code || "creada"}`);
      closeModal();
      showSection("taller");
      await loadTaller();
      await openTallerJob(id);
      loadDashboard();
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
  paintUser(u);
  api("/api/me")
    .then((me) => paintUser(me))
    .catch(() => {});
  document.getElementById("logoutBtn")?.addEventListener("click", () => {
    localStorage.clear();
    location.href = "/login";
  });
  document.querySelectorAll("#nav button").forEach((btn) => {
    btn.addEventListener("click", () => showSection(btn.dataset.section));
  });
  document.querySelectorAll("[data-go]").forEach((btn) => {
    btn.addEventListener("click", () => showSection(btn.dataset.go));
  });
  document.getElementById("moduleHubGrid")?.addEventListener("click", (e) => {
    const card = e.target.closest("[data-go]");
    if (card) showSection(card.dataset.go);
  });
  document.getElementById("refreshBoard")?.addEventListener("click", () => loadDashboard().catch((e) => toast(e.message)));
  document.getElementById("refreshTallerBtn")?.addEventListener("click", () => loadTaller());
  document.getElementById("marketSearchBtn")?.addEventListener("click", () => runMarketSearch());
  document.getElementById("marketQuery")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") runMarketSearch();
  });
  document.getElementById("refreshAllyJobsBtn")?.addEventListener("click", () => loadAliados());
  document.getElementById("newAllyJobBtn")?.addEventListener("click", () => openNewAllyJob());
  document.getElementById("newAllyBtn")?.addEventListener("click", () => openNewSupplier("aliado"));
  const partSearchBtn = document.getElementById("partSearchBtn");
  const onlyLow = document.getElementById("onlyLow");
  const partSearch = document.getElementById("partSearch");
  if (partSearchBtn) partSearchBtn.onclick = () => loadParts().catch((e) => toast(e.message));
  if (onlyLow) onlyLow.onchange = () => loadParts().catch((e) => toast(e.message));
  partSearch?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") loadParts().catch((err) => toast(err.message));
  });
  document.getElementById("modal")?.addEventListener("click", (e) => {
    if (e.target.id === "modal") closeModal();
  });
  const receivedBy = document.getElementById("receivedBy");
  if (receivedBy) receivedBy.value = u.name;

  document.getElementById("receptionForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("submitIntakeBtn");
    try {
      if (!arrivalPhotoFiles.length) {
        const ok = confirm("No hay fotos. ¿Cerrar el ingreso sin fotos?");
        if (!ok) return;
      }
      if (!signaturePad?.isDirty()) {
        const ok = confirm("No hay firma dibujada. ¿Continuar solo con el nombre?");
        if (!ok) return;
      }
      if (!e.target.checkValidity()) {
        e.target.reportValidity();
        toast("Complete los campos obligatorios (nombre, placa, marca, modelo, queja, firma y aceptación)");
        return;
      }
      const fd = new FormData(e.target);
      const zones = [...document.querySelectorAll("#zoneGrid .zone-chip.active")].map((el) => el.dataset.zone);
      const damageNotes = String(fd.get("damage_notes") || "");
      const modelVal = String(fd.get("model_other") || fd.get("model") || "").trim();
      const body = {
        customer: {
          name: String(fd.get("customer_name") || "").trim(),
          phone: String(fd.get("customer_phone") || "").trim(),
          id_number: String(fd.get("customer_id_number") || "").trim(),
        },
        plate: String(fd.get("plate") || "").toUpperCase().trim(),
        brand: String(fd.get("brand") || "").trim(),
        model: modelVal === "Otro" ? String(fd.get("model_other") || "").trim() : modelVal,
        year: Number(fd.get("year") || 0),
        color: String(fd.get("color") || "").trim(),
        odometer_km: Number(fd.get("odometer_km") || 0),
        fuel_level: String(fd.get("fuel_level") || "1/2"),
        promised_hours: Number(fd.get("promised_hours") || 24),
        customer_complaint: String(fd.get("customer_complaint") || "").trim(),
        accessories: String(fd.get("accessories") || "").trim(),
        received_by: String(fd.get("received_by") || user()?.name || "").trim(),
        customer_signature_name: String(fd.get("customer_signature_name") || "").trim(),
        customer_accepted: fd.get("customer_accepted") === "on",
        damages: zones.map((zone) => ({
          zone,
          severity: "leve",
          description: damageNotes,
          present_on_arrival: true,
        })),
      };
      if (!body.customer.name || !body.plate || !body.brand || !body.model || !body.customer_complaint) {
        toast("Falta nombre, placa, marca, modelo o qué trae el carro");
        return;
      }
      if (!body.customer_accepted) {
        toast("Marque que el cliente acepta el estado de ingreso");
        return;
      }
      if (!body.damages.length && damageNotes) {
        body.damages = [{ zone: "Otro", severity: "leve", description: damageNotes, present_on_arrival: true }];
      }
      if (btn) {
        btn.disabled = true;
        btn.textContent = "Guardando ingreso…";
      }
      const created = await api("/api/receptions", { method: "POST", body: JSON.stringify(body) });
      const mediaErrors = await uploadArrivalMedia(created.id);
      if (mediaErrors.length) {
        toast(`Ingreso ${created.code} listo · fotos/firma parcial: ${mediaErrors[0]}`);
      } else {
        toast(`Ingreso ${created.code} listo — en el patio`);
      }
      e.target.reset();
      arrivalPhotoFiles.length = 0;
      renderPhotoPreviews();
      signaturePad?.clear();
      document.querySelectorAll("#zoneGrid .zone-chip.active").forEach((el) => el.classList.remove("active"));
      const rb = document.getElementById("receivedBy");
      if (rb) rb.value = user()?.name || "";
      loadReceptions();
      loadDashboard();
      if (typeof loadTaller === "function") loadTaller();
      try {
        await openReception(created.id);
      } catch (openErr) {
        console.warn(openErr);
        toast(`Ingreso ${created.code} guardado. Ábralo desde la lista.`);
      }
    } catch (err) {
      toast(err.message || "No se pudo cerrar el ingreso");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Cerrar ingreso y meter al patio";
      }
    }
  });

  document.getElementById("settingsForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const fd = new FormData(e.target);
      const body = Object.fromEntries(fd.entries());
      body.labor_rate = Number(body.labor_rate || 0);
      await api("/api/settings", { method: "PUT", body: JSON.stringify(body) });
      toast("Configuración guardada");
      loadSettings();
    } catch (err) {
      toast(err.message);
    }
  });

  document.getElementById("newPartBtn")?.addEventListener("click", async () => {
    openModal(`
      <h2>Nuevo repuesto</h2>
      <form id="partForm" class="form-grid">
        <label>SKU<input name="sku" required placeholder="Interno" /></label>
        <label>Código de barras<input name="barcode" placeholder="Escanee aquí con la pistola" /></label>
        <label class="full">Nombre<input name="name" required /></label>
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
    const bar = document.querySelector('#partForm [name="barcode"]');
    bar?.focus();
    document.getElementById("partForm").onsubmit = async (ev) => {
      ev.preventDefault();
      const fd = new FormData(ev.target);
      const body = Object.fromEntries(fd.entries());
      ["stock_qty", "min_stock", "cost_price", "sale_price"].forEach((k) => (body[k] = Number(body[k] || 0)));
      body.preferred_supplier_id = body.preferred_supplier_id ? Number(body.preferred_supplier_id) : null;
      body.barcode = (body.barcode || "").trim() || body.sku;
      await api("/api/parts", { method: "POST", body: JSON.stringify(body) });
      toast("Repuesto creado");
      closeModal();
      loadParts();
    };
  });

  document.getElementById("issuerForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const body = Object.fromEntries(new FormData(e.target).entries());
      if (!body.hacienda_password) delete body.hacienda_password;
      if (!body.pin_cert) delete body.pin_cert;
      await api("/api/fe/issuer", { method: "PUT", body: JSON.stringify(body) });
      toast("Emisor Hacienda guardado");
      loadFacturacion();
    } catch (err) {
      toast(err.message || "No se pudo guardar el emisor");
    }
  });

  document.getElementById("testHaciendaBtn")?.addEventListener("click", async () => {
    try {
      const res = await api("/api/fe/test-auth", { method: "POST", body: "{}" });
      toast(`Auth Hacienda OK (${res.environment})`);
    } catch (err) {
      toast(err.message);
    }
  });

  document.getElementById("refreshFeReadyBtn")?.addEventListener("click", () => loadFeReadiness());

  document.getElementById("certForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const fd = new FormData(e.target);
      const res = await fetch("/api/fe/cert", {
        method: "POST",
        headers: { Authorization: `Bearer ${token()}` },
        body: fd,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "No se pudo subir el certificado");
      toast(data.subject ? `Certificado OK · ${data.subject}` : "Certificado cargado");
      e.target.reset();
      loadFacturacion();
    } catch (err) {
      toast(err.message);
    }
  });

  document.getElementById("issueFeBtn")?.addEventListener("click", async () => {
    try {
    let ready = null;
    try {
      ready = await api("/api/fe/readiness");
    } catch (_) {}
    const feReady = !!(ready && ready.ready);
    if (!feReady) {
      const missing = (ready?.missing || []).join(", ") || "ATV / certificado .p12";
      toast(`Puede armar el comprobante; para Hacienda falta: ${missing}`);
    }
    const taller = await api("/api/receptions");
    const withOt = taller.filter((r) => r.work_order);
    if (!withOt.length) {
      toast("Primero cree una OT en Diagnóstico & OT");
      showSection("taller");
      return;
    }
    openModal(`
      <h2>Emitir factura / tiquete</h2>
      <p class="muted">${feReady ? "Listo para firmar y enviar a Hacienda." : "Sin certificado ATV completo: genere el XML (sin enviar) o complete Emisor + .p12."}</p>
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
        <label class="full" style="flex-direction:row;align-items:center;gap:8px">
          <input type="checkbox" name="send_now" ${feReady ? "checked" : ""} style="width:auto" ${feReady ? "" : "disabled"} />
          Firmar y enviar a Hacienda ahora ${feReady ? "" : "(requiere ATV + .p12)"}
        </label>
        <div class="full row-actions">
          <button class="btn btn-primary" type="submit">Procesar comprobante</button>
          <button class="btn btn-ghost" type="button" id="closeModalBtn">Cancelar</button>
        </div>
      </form>
    `);
    document.getElementById("closeModalBtn").onclick = closeModal;
    document.getElementById("feIssueForm").onsubmit = async (ev) => {
      ev.preventDefault();
      try {
        const body = Object.fromEntries(new FormData(ev.target).entries());
        body.work_order_id = Number(body.work_order_id);
        body.send_now = body.send_now === "on";
        toast(body.send_now ? "Firmando y consultando Hacienda…" : "Generando XML…");
        const res = await api("/api/fe/issue", { method: "POST", body: JSON.stringify(body) });
        if (res.invoice || res.clave) {
          const inv = res.invoice || res;
          toast(res.message || `Comprobante ${String(inv.clave || "").slice(0, 12)}… · ${inv.status || ""}`);
        } else {
          toast(res.message || "Comprobante procesado");
        }
        closeModal();
        loadFacturacion();
        showSection("facturacion");
      } catch (err) {
        toast(err.message);
      }
    };
    } catch (err) {
      toast(err.message || "No se pudo abrir facturación");
    }
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

  document.getElementById("newSupplierBtn")?.addEventListener("click", () => openNewSupplier("tienda"));

  bindBarcodeScanner();

  const safeInit = (fn, label) => {
    try {
      fn();
    } catch (err) {
      console.error(label, err);
      toast(`${label}: ${err.message || "falló el arranque"}`);
    }
  };
  safeInit(initZones, "Zonas");
  safeInit(initIntakeVehicleOptions, "Marcas");
  safeInit(initArrivalPhotos, "Fotos");
  safeInit(initSignaturePad, "Firma");
  loadSettings().catch((err) => toast(err.message || "No se pudo cargar identidad"));
  // Patio primero: el cliente ve carros y estaciones, no una pantalla de marketing
  showSection("tablero");
  setTimeout(() => resizeSignaturePad(false), 80);
}

try {
  bindUI();
} catch (err) {
  console.error(err);
  const el = document.getElementById("toast");
  if (el) {
    el.textContent = "Error al iniciar Katire. Recargue la página (Ctrl+F5).";
    el.classList.add("show");
  }
}
