/* Diagnóstico: croqui digital del carro (todas las piezas) + marcar + imprimir */

function tallerZoneClass(stateByKey, key) {
  return (stateByKey[key] && stateByKey[key].status) || "na";
}

/** Croquis vista superior — piezas clicables */
function tallerCarMapHtml(stateByKey) {
  const c = (k) => tallerZoneClass(stateByKey, k);
  const hit = (k, shape, label, lx, ly) => `
    <g class="zone-group" data-key="${k}">
      ${shape}
      <text class="zone-label" x="${lx}" y="${ly}" text-anchor="middle" pointer-events="none">${label}</text>
    </g>`;

  return `
  <div class="croqui-wrap">
    <svg class="car-svg taller-car-svg croqui-svg" viewBox="0 0 280 520" xmlns="http://www.w3.org/2000/svg" aria-label="Croqui digital del vehículo">
      <!-- Silueta del carro -->
      <path class="car-body" d="M70 40
        Q140 8 210 40
        L230 90
        Q248 140 248 220
        L248 360
        Q248 430 220 470
        Q140 505 60 470
        Q32 430 32 360
        L32 220
        Q32 140 50 90
        Z" />
      <path class="car-glass" d="M78 175 L202 175 L190 250 L90 250 Z" />
      <path class="car-glass rear" d="M90 310 L190 310 L200 360 L80 360 Z" />
      <ellipse class="car-wheel" cx="38" cy="150" rx="14" ry="28" />
      <ellipse class="car-wheel" cx="242" cy="150" rx="14" ry="28" />
      <ellipse class="car-wheel" cx="38" cy="380" rx="14" ry="28" />
      <ellipse class="car-wheel" cx="242" cy="380" rx="14" ry="28" />

      ${hit(
        "frente",
        `<path class="zone ${c("frente")}" data-key="frente" d="M78 28 Q140 6 202 28 L218 70 L62 70 Z"/>`,
        "FRENTE",
        140,
        52
      )}
      ${hit(
        "luces",
        `<rect class="zone ${c("luces")}" data-key="luces" x="58" y="62" width="36" height="22" rx="5"/>
         <rect class="zone ${c("luces")}" data-key="luces" x="186" y="62" width="36" height="22" rx="5"/>`,
        "LUCES",
        140,
        78
      )}
      ${hit(
        "capot",
        `<rect class="zone ${c("capot")}" data-key="capot" x="70" y="88" width="140" height="48" rx="8"/>`,
        "CAPÓ",
        140,
        116
      )}
      ${hit(
        "motor",
        `<rect class="zone ${c("motor")}" data-key="motor" x="88" y="98" width="104" height="32" rx="6"/>`,
        "MOTOR",
        140,
        118
      )}
      ${hit(
        "fluidos",
        `<rect class="zone ${c("fluidos")}" data-key="fluidos" x="96" y="132" width="88" height="18" rx="4"/>`,
        "FLUIDOS",
        140,
        145
      )}
      ${hit(
        "parabrisas",
        `<path class="zone ${c("parabrisas")}" data-key="parabrisas" d="M78 155 L202 155 L192 190 L88 190 Z"/>`,
        "PARABRISAS",
        140,
        178
      )}
      ${hit(
        "techo",
        `<rect class="zone ${c("techo")}" data-key="techo" x="88" y="198" width="104" height="52" rx="8"/>`,
        "TECHO",
        140,
        228
      )}
      ${hit(
        "aire",
        `<rect class="zone ${c("aire")}" data-key="aire" x="100" y="208" width="80" height="20" rx="4"/>`,
        "A/C",
        140,
        222
      )}
      ${hit(
        "interior",
        `<rect class="zone ${c("interior")}" data-key="interior" x="96" y="232" width="88" height="36" rx="6"/>`,
        "INTERIOR",
        140,
        254
      )}
      ${hit(
        "direccion",
        `<rect class="zone ${c("direccion")}" data-key="direccion" x="100" y="272" width="42" height="28" rx="5"/>`,
        "DIR.",
        121,
        290
      )}
      ${hit(
        "electrico",
        `<rect class="zone ${c("electrico")}" data-key="electrico" x="148" y="272" width="42" height="28" rx="5"/>`,
        "ELEC.",
        169,
        290
      )}
      ${hit(
        "transmision",
        `<rect class="zone ${c("transmision")}" data-key="transmision" x="108" y="308" width="64" height="28" rx="6"/>`,
        "CAJA",
        140,
        326
      )}
      ${hit(
        "suspension",
        `<rect class="zone ${c("suspension")}" data-key="suspension" x="52" y="330" width="30" height="70" rx="6"/>
         <rect class="zone ${c("suspension")}" data-key="suspension" x="198" y="330" width="30" height="70" rx="6"/>`,
        "SUSP.",
        140,
        360
      )}
      ${hit(
        "frenos",
        `<circle class="zone ${c("frenos")}" data-key="frenos" cx="55" cy="150" r="16"/>
         <circle class="zone ${c("frenos")}" data-key="frenos" cx="225" cy="150" r="16"/>
         <circle class="zone ${c("frenos")}" data-key="frenos" cx="55" cy="380" r="16"/>
         <circle class="zone ${c("frenos")}" data-key="frenos" cx="225" cy="380" r="16"/>`,
        "FRENOS",
        140,
        400
      )}
      ${hit(
        "llantas",
        `<ellipse class="zone ${c("llantas")}" data-key="llantas" cx="38" cy="150" rx="12" ry="24"/>
         <ellipse class="zone ${c("llantas")}" data-key="llantas" cx="242" cy="150" rx="12" ry="24"/>
         <ellipse class="zone ${c("llantas")}" data-key="llantas" cx="38" cy="380" rx="12" ry="24"/>
         <ellipse class="zone ${c("llantas")}" data-key="llantas" cx="242" cy="380" rx="12" ry="24"/>`,
        "LLANTAS",
        140,
        420
      )}
      ${hit(
        "lateral_izq",
        `<path class="zone ${c("lateral_izq")}" data-key="lateral_izq" d="M34 120 L62 110 L62 400 L34 390 Z"/>`,
        "IZQ",
        48,
        260
      )}
      ${hit(
        "lateral_der",
        `<path class="zone ${c("lateral_der")}" data-key="lateral_der" d="M218 110 L246 120 L246 390 L218 400 Z"/>`,
        "DER",
        232,
        260
      )}
      ${hit(
        "escape",
        `<rect class="zone ${c("escape")}" data-key="escape" x="122" y="430" width="36" height="28" rx="5"/>`,
        "ESCAPE",
        140,
        448
      )}
      ${hit(
        "trasera",
        `<path class="zone ${c("trasera")}" data-key="trasera" d="M70 455 Q140 492 210 455 L218 430 L62 430 Z"/>`,
        "TRASERA",
        140,
        462
      )}
      ${hit(
        "carroceria",
        `<rect class="zone ${c("carroceria")}" data-key="carroceria" x="108" y="348" width="64" height="22" rx="5"/>`,
        "CARROCERÍA",
        140,
        363
      )}

      <text x="140" y="22" text-anchor="middle" class="croqui-title" pointer-events="none">↑ FRENTE</text>
      <text x="140" y="512" text-anchor="middle" class="croqui-title" pointer-events="none">TRASERA ↓</text>
    </svg>
    <div class="croqui-legend">
      <span><i class="dot ok"></i>OK</span>
      <span><i class="dot watch"></i>Vigilar</span>
      <span><i class="dot fail"></i>Falla</span>
      <span><i class="dot na"></i>Sin revisar</span>
      <span class="muted">Toque una pieza para marcar</span>
    </div>
  </div>`;
}

async function openTallerJob(id) {
  tallerActiveId = id;
  const ws = document.getElementById("tallerWorkspace");
  if (!ws) return;
  document.querySelectorAll("#tallerList .taller-card").forEach((el) => {
    el.classList.toggle("active", Number(el.dataset.id) === id);
  });
  ws.innerHTML = `<div class="empty-state"><strong>Cargando croqui del carro…</strong></div>`;
  try {
    // Completa piezas nuevas del croqui si faltan
    try {
      await api("/api/bootstrap/workspace", { method: "POST", body: "{}" });
    } catch (_) {}

    const r = await api(`/api/receptions/${id}`);
    const v = r.vehicle || {};
    const c = v.customer || {};
    const d = r.diagnosis || {};
    const wo = r.work_order;
    let checks = r.inspection || [];

    // Si el ingreso es viejo y no tiene todas las piezas, forzar seed vía PUT no-op + reload
    if (checks.length < 12) {
      try {
        await api(`/api/receptions/${id}/inspection`, {
          method: "PUT",
          body: JSON.stringify({
            items: checks.map((ch) => ({
              system_key: ch.system_key,
              status: ch.status || "na",
              notes: ch.notes || "",
            })),
          }),
        });
        const r2 = await api(`/api/receptions/${id}`);
        checks = r2.inspection || checks;
      } catch (_) {}
    }

    const dviState = {};
    checks.forEach((ch) => {
      dviState[ch.system_key] = {
        status: ch.status || "na",
        notes: ch.notes || "",
        name: ch.system_name,
      };
    });

    const failCount = () => Object.values(dviState).filter((x) => x.status === "fail").length;
    const watchCount = () => Object.values(dviState).filter((x) => x.status === "watch").length;

    const paintMap = () => {
      const box = document.getElementById("tallerCarMap");
      if (box) box.innerHTML = tallerCarMapHtml(dviState);
      box?.querySelectorAll(".zone").forEach((el) => {
        el.addEventListener("click", (ev) => {
          ev.stopPropagation();
          cycleZone(el.dataset.key);
        });
      });
      const sum = document.getElementById("dviSummaryLine");
      if (sum) {
        sum.innerHTML = `<span class="badge badge-low">${failCount()} fallas</span>
          <span class="badge badge-en_diagnostico">${watchCount()} vigilar</span>
          <span class="muted">Ciclo al tocar: Sin revisar → OK → Vigilar → Falla</span>`;
      }
      ws.querySelectorAll(".dvi-item").forEach((item) => {
        const key = item.dataset.key;
        const st = dviState[key]?.status || "na";
        item.classList.toggle("active", st === "fail" || st === "watch");
        item.querySelectorAll("button[data-st]").forEach((b) => {
          b.className = "";
          if (b.dataset.st === st) b.classList.add(`on-${st}`);
        });
      });
    };

    const cycleZone = (key) => {
      if (!dviState[key]) {
        // pieza del croqui aún no en checklist: crear en memoria
        dviState[key] = { status: "fail", notes: "", name: key };
      }
      const order = ["na", "ok", "watch", "fail"];
      const i = order.indexOf(dviState[key].status || "na");
      dviState[key].status = order[(i + 1) % order.length];
      paintMap();
      document.querySelector(`.dvi-item[data-key="${key}"]`)?.scrollIntoView({ block: "nearest" });
    };

    const syncFindingsFromMap = () => {
      const fails = Object.entries(dviState)
        .filter(([, x]) => x.status === "fail" || x.status === "watch")
        .map(
          ([k, x]) =>
            `${x.name || k}: ${x.status === "fail" ? "FALLA" : "vigilar"}${x.notes ? ` — ${x.notes}` : ""}`
        );
      const findings = document.querySelector("#tallerDiagForm textarea[name='findings']");
      const work = document.querySelector("#tallerDiagForm textarea[name='recommended_work']");
      if (findings && !String(findings.value || "").trim() && fails.length) {
        findings.value = fails.join("\n");
      }
      if (work && !String(work.value || "").trim() && fails.length) {
        work.value = `Atender: ${fails.map((f) => f.split(":")[0]).join(", ")}`;
      }
    };

    const saveInspection = async () => {
      await api(`/api/receptions/${id}/inspection`, {
        method: "PUT",
        body: JSON.stringify({
          items: Object.entries(dviState).map(([system_key, x]) => ({
            system_key,
            status: x.status,
            notes: x.notes || "",
          })),
        }),
      });
    };

    const printDiagnosis = async () => {
      await saveInspection();
      const res = await fetch(`/api/receptions/${id}/diagnosis/print`, {
        headers: { Authorization: `Bearer ${token()}` },
      });
      if (!res.ok) throw new Error("No se pudo generar la impresión del croqui");
      const html = await res.text();
      const w = window.open("", "_blank");
      if (!w) throw new Error("Permita ventanas emergentes para imprimir");
      w.document.write(html);
      w.document.close();
    };

    ws.innerHTML = `
      <div class="panel-head" style="margin-bottom:12px">
        <div>
          <h2 style="margin:0;font-family:var(--display)">${esc(v.plate)} · ${esc(v.brand)} ${esc(v.model)}</h2>
          <p class="muted" style="margin:6px 0 0">${esc(r.code)} · ${esc(c.name || "")} · ${badge(r.status)}</p>
          <p style="margin:10px 0 0"><strong>Queja:</strong> ${esc(r.customer_complaint || "—")}</p>
        </div>
        <div class="row-actions">
          <button class="btn btn-primary" id="printDiagBtn" type="button">Imprimir croqui + firma</button>
          <button class="btn btn-ghost" id="buyPartsBtn" type="button">Buscar repuestos</button>
          <button class="btn btn-ghost" id="sendAllyBtn" type="button">Enviar a aliado</button>
        </div>
      </div>

      <div class="taller-dvi-layout">
        <div>
          <h3 style="margin-top:0">1 · Croqui del vehículo</h3>
          <p class="muted" style="margin-top:0">Toque cada pieza del carro para marcar. Luego imprima para que el cliente firme.</p>
          <div id="tallerCarMap">${tallerCarMapHtml(dviState)}</div>
          <div id="dviSummaryLine" class="row-actions" style="margin-top:10px"></div>
        </div>
        <div>
          <h3 style="margin-top:0">Lista de piezas</h3>
          <div class="dvi-items taller-dvi-list" id="dviGrid">
            ${
              checks
                .map(
                  (ch) => `
              <div class="dvi-item" data-key="${esc(ch.system_key)}">
                <div>
                  <strong class="name">${esc(ch.system_name)}</strong>
                  <input class="dvi-note" data-key="${esc(ch.system_key)}" value="${esc(ch.notes || "")}" placeholder="Nota de la falla…" style="margin-top:6px;width:100%" />
                </div>
                <div class="dvi-actions lights">
                  <button type="button" data-st="ok">OK</button>
                  <button type="button" data-st="watch">!</button>
                  <button type="button" data-st="fail">X</button>
                  <button type="button" data-st="na">—</button>
                </div>
              </div>`
                )
                .join("") || `<div class="muted">Sin checklist — abra de nuevo el vehículo</div>`
            }
          </div>
          <div class="row-actions" style="margin-top:10px">
            <button class="btn btn-ghost" id="saveDviBtn" type="button">Guardar croqui</button>
            <button class="btn btn-ok" id="fillFromMapBtn" type="button">Pasar fallas al diagnóstico</button>
            <button class="btn btn-primary" id="printBeforeAssignBtn2" type="button">Imprimir</button>
          </div>
        </div>
      </div>

      <h3>2 · Diagnóstico y autorización</h3>
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
        <label class="full">Trabajo recomendado<textarea name="recommended_work" required placeholder="Ej. Cambio de pastillas delanteras">${esc(d.recommended_work || "")}</textarea></label>
        <label>Horas estimadas<input name="estimated_hours" type="number" step="0.25" min="0.25" value="${esc(d.estimated_hours || 1)}" required /></label>
        <div class="full row-actions">
          <button class="btn btn-ghost" type="button" id="printBeforeAssignBtn">Imprimir croqui para firma</button>
          <button class="btn btn-primary" type="submit" id="saveDiagBtn">Asignar al taller (crear OT)</button>
        </div>
        <p class="full muted" style="margin:0">Flujo: marque piezas en el croqui → imprima y firme el cliente → Asignar al taller.</p>
      </form>

      <div id="tallerOtBox" style="margin-top:18px">
        ${
          wo
            ? `
          <h3>3 · Orden de trabajo ${esc(wo.code)}</h3>
          <p class="muted">Mano de obra: ${money(wo.labor_total)} · Repuestos: ${money(wo.parts_total)} · <strong>Total ${money(wo.grand_total)}</strong></p>
          <p>${esc(wo.labor_notes || d.recommended_work || "")}</p>
          <ul>${(wo.lines || []).map((l) => `<li>${esc(l.description)} × ${l.quantity} · ${badge(l.status)} · ${money(l.line_total)}</li>`).join("") || "<li class='muted'>Sin repuestos aún</li>"}</ul>
          <div class="row-actions">
            <button class="btn btn-warn" id="otToShopBtn" type="button">Meter a reparación</button>
            <button class="btn btn-ghost" id="otOpenFicha" type="button">Ver ficha completa</button>
          </div>`
            : `<p class="muted" style="margin-top:14px">Sin OT aún. Al asignar al taller se crea la orden automáticamente.</p>`
        }
        ${typeof avanceControlsHtml === "function" ? avanceControlsHtml(r.status) : ""}
      </div>
    `;

    paintMap();

    ws.querySelectorAll(".dvi-item").forEach((item) => {
      const key = item.dataset.key;
      item.querySelectorAll("button[data-st]").forEach((btn) => {
        btn.onclick = () => {
          if (!dviState[key]) return;
          dviState[key].status = btn.dataset.st;
          paintMap();
        };
      });
      item.querySelector(".dvi-note")?.addEventListener("input", (ev) => {
        if (dviState[key]) dviState[key].notes = ev.target.value;
      });
    });

    document.getElementById("saveDviBtn").onclick = async () => {
      try {
        await saveInspection();
        toast("Croqui guardado");
        loadDashboard();
      } catch (err) {
        toast(err.message || "No se pudo guardar el croqui");
      }
    };
    document.getElementById("fillFromMapBtn")?.addEventListener("click", () => {
      syncFindingsFromMap();
      toast("Fallas pasadas al diagnóstico");
    });

    document.getElementById("tallerDiagForm").onsubmit = async (ev) => {
      ev.preventDefault();
      const btn = document.getElementById("saveDiagBtn");
      try {
        if (btn) {
          btn.disabled = true;
          btn.textContent = "Asignando…";
        }
        syncFindingsFromMap();
        await saveInspection();
        const fd = new FormData(ev.target);
        const body = Object.fromEntries(fd.entries());
        body.estimated_hours = Number(body.estimated_hours || 1);
        body.create_work_order = true;
        const res = await api(`/api/receptions/${id}/diagnosis`, {
          method: "POST",
          body: JSON.stringify(body),
        });
        await api(`/api/receptions/${id}/status`, {
          method: "PATCH",
          body: JSON.stringify({ status: "en_reparacion" }),
        });
        toast(`Asignado al taller · OT ${res.work_order?.code || "creada"}`);
        loadDashboard();
        await loadTaller();
        await openTallerJob(id);
      } catch (err) {
        toast(err.message || "No se pudo asignar al taller");
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.textContent = "Asignar al taller (crear OT)";
        }
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
    document.getElementById("otToShopBtn")?.addEventListener("click", () => patch("en_reparacion"));
    document.getElementById("otOpenFicha")?.addEventListener("click", () => openReception(id));

    const doPrint = async () => {
      try {
        await printDiagnosis();
        toast("Imprima el croqui y pida firma al cliente");
      } catch (err) {
        toast(err.message);
      }
    };
    document.getElementById("printDiagBtn")?.addEventListener("click", doPrint);
    document.getElementById("printBeforeAssignBtn")?.addEventListener("click", async () => {
      syncFindingsFromMap();
      await doPrint();
    });
    document.getElementById("printBeforeAssignBtn2")?.addEventListener("click", doPrint);

    document.getElementById("buyPartsBtn")?.addEventListener("click", () => {
      const q = [d.recommended_work, v.brand, v.model, v.year].filter(Boolean).join(" ");
      showSection("proveedores");
      const mq = document.getElementById("marketQuery");
      const mv = document.getElementById("marketVehicle");
      if (mq) mq.value = q || "";
      if (mv) mv.value = `${v.plate || ""} ${v.brand || ""} ${v.model || ""}`.trim();
      if (typeof runMarketSearch === "function") runMarketSearch();
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
    ws.innerHTML = `<div class="empty-state"><strong>Error</strong>${esc(err.message || "No se pudo abrir el diagnóstico")}</div>`;
    toast(err.message || "Error al abrir diagnóstico");
  }
}
