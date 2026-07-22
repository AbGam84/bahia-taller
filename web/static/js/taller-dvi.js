/* Diagnóstico: mapa digital del carro + impresión con firma + asignación al taller */

function tallerCarMapHtml(stateByKey) {
  const cls = (k) => (stateByKey[k] && stateByKey[k].status) || "na";
  const zones = [
    ["luces", 70, 18, 60, 22, "Luces"],
    ["carroceria", 45, 48, 110, 90, "Carrocería"],
    ["motor", 60, 55, 80, 40, "Motor"],
    ["fluidos", 78, 70, 44, 18, "Fluidos"],
    ["aire", 70, 100, 60, 28, "A/C"],
    ["direccion", 55, 145, 40, 36, "Dirección"],
    ["electrico", 105, 145, 40, 36, "Eléctrico"],
    ["transmision", 70, 188, 60, 30, "Caja"],
    ["suspension", 40, 188, 24, 55, "Susp."],
    ["suspension", 136, 188, 24, 55, "Susp."],
    ["frenos", 38, 250, 28, 28, "Freno"],
    ["frenos", 134, 250, 28, 28, "Freno"],
    ["escape", 85, 250, 30, 40, "Escape"],
    ["llantas", 36, 282, 32, 22, "Llanta"],
    ["llantas", 132, 282, 32, 22, "Llanta"],
  ];
  return `
  <svg class="car-svg taller-car-svg" viewBox="0 0 200 320" xmlns="http://www.w3.org/2000/svg" aria-label="Mapa digital del carro">
    ${zones
      .map(
        ([k, x, y, w, h, label]) => `
      <g class="zone-group" data-key="${k}">
        <rect class="zone ${cls(k)}" data-key="${k}" x="${x}" y="${y}" width="${w}" height="${h}" rx="6"/>
        <text x="${x + w / 2}" y="${y + h / 2 + 3}" text-anchor="middle" fill="#eef7f4" font-size="7" font-family="Manrope,sans-serif" pointer-events="none">${label}</text>
      </g>`
      )
      .join("")}
  </svg>`;
}

async function openTallerJob(id) {
  tallerActiveId = id;
  const ws = document.getElementById("tallerWorkspace");
  if (!ws) return;
  document.querySelectorAll("#tallerList .taller-card").forEach((el) => {
    el.classList.toggle("active", Number(el.dataset.id) === id);
  });
  ws.innerHTML = `<div class="empty-state"><strong>Cargando mapa del carro…</strong></div>`;
  try {
    const r = await api(`/api/receptions/${id}`);
    const v = r.vehicle || {};
    const c = v.customer || {};
    const d = r.diagnosis || {};
    const wo = r.work_order;
    const checks = r.inspection || [];
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
        el.addEventListener("click", () => cycleZone(el.dataset.key));
      });
      const sum = document.getElementById("dviSummaryLine");
      if (sum) {
        sum.innerHTML = `<span class="badge badge-low">${failCount()} fallas</span>
          <span class="badge badge-en_diagnostico">${watchCount()} vigilar</span>
          <span class="muted">Toque una parte: OK → Vigilar → Falla → Sin revisar</span>`;
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
      if (!dviState[key]) return;
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
      if (!res.ok) throw new Error("No se pudo generar la impresión");
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
          <button class="btn btn-ghost" id="printDiagBtn">Imprimir + firma cliente</button>
          <button class="btn btn-ghost" id="buyPartsBtn">Buscar repuestos</button>
          <button class="btn btn-ghost" id="sendAllyBtn">Enviar a aliado</button>
        </div>
      </div>

      <div class="taller-dvi-layout">
        <div>
          <h3 style="margin-top:0">1 · Mapa digital del carro</h3>
          <p class="muted" style="margin-top:0">Toque cada parte para marcar fallas. Verde OK · Amarillo vigilar · Rojo falla.</p>
          <div id="tallerCarMap">${tallerCarMapHtml(dviState)}</div>
          <div id="dviSummaryLine" class="row-actions" style="margin-top:10px"></div>
        </div>
        <div>
          <h3 style="margin-top:0">Partes del vehículo</h3>
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
                .join("") || `<div class="muted">Sin checklist — vuelva a abrir el ingreso</div>`
            }
          </div>
          <div class="row-actions" style="margin-top:10px">
            <button class="btn btn-ghost" id="saveDviBtn">Guardar mapa</button>
            <button class="btn btn-ok" id="fillFromMapBtn">Pasar fallas al diagnóstico</button>
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
          <button class="btn btn-ghost" type="button" id="printBeforeAssignBtn">Imprimir para firma</button>
          <button class="btn btn-primary" type="submit" id="saveDiagBtn">Asignar al taller (crear OT)</button>
        </div>
        <p class="full muted" style="margin:0">Flujo: marque fallas → imprima y firme el cliente → Asignar al taller.</p>
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
            <button class="btn btn-warn" id="otToShopBtn">Meter a reparación</button>
            <button class="btn btn-ghost" id="otOpenFicha">Ver ficha completa</button>
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
        toast("Mapa de fallas guardado");
        loadDashboard();
      } catch (err) {
        toast(err.message || "No se pudo guardar el mapa");
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
    document.getElementById("printDiagBtn")?.addEventListener("click", async () => {
      try {
        await printDiagnosis();
        toast("Imprima y pida firma al cliente");
      } catch (err) {
        toast(err.message);
      }
    });
    document.getElementById("printBeforeAssignBtn")?.addEventListener("click", async () => {
      try {
        syncFindingsFromMap();
        await printDiagnosis();
        toast("Hoja lista para firma del cliente");
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
