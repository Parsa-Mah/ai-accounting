// pages/audit.js — audit trail: every committed write to the books,
// who did it and when. Read-only; the trail is append-only server-side.
//
// actor/model/action are machine identifiers (e.g. "user:1", "JournalEntry",
// "create"), so they render as-is in mono — like the raw values elsewhere
// in the app — rather than being translated.
import { API } from "../api.js";
import { fmtDateTime, esc, toast } from "../ui.js";
import { t } from "../i18n.js";

const ACTIONS = ["create", "update", "delete"];

export default {
  async render(container) {
    container.innerHTML = `
      <div class="page-head">
        <div>
          <h1 class="page-title">${t("nav.audit")}</h1>
          <p class="page-sub">${t("audit.subtitle")}</p>
        </div>
      </div>

      <div class="card">
        <div class="toolbar">
          <label class="field"><span>${t("audit.actor")}</span>
            <input id="f-actor" autocomplete="off" /></label>
          <label class="field"><span>${t("audit.model")}</span>
            <input id="f-model" autocomplete="off" /></label>
          <label class="field"><span>${t("audit.action")}</span>
            <select id="f-action">
              <option value="">${t("audit.all_actions")}</option>
              ${ACTIONS.map((a) => `<option value="${a}">${a}</option>`).join("")}
            </select>
          </label>
          <label class="field"><span>${t("common.from")}</span>
            <input type="date" id="f-from" /></label>
          <label class="field"><span>${t("common.to")}</span>
            <input type="date" id="f-to" /></label>
          <label class="field"><span>${t("audit.limit")}</span>
            <input type="number" id="f-limit" value="200" min="1" max="1000" /></label>
          <button id="f-refresh" class="btn" type="button">${t("common.refresh")}</button>
        </div>
        <div id="audit-body"><div class="empty">${t("common.loading")}</div></div>
      </div>
    `;

    const body = container.querySelector("#audit-body");

    async function load() {
      const params = {};
      const actor = container.querySelector("#f-actor").value.trim();
      const model = container.querySelector("#f-model").value.trim();
      const action = container.querySelector("#f-action").value;
      const from = container.querySelector("#f-from").value;
      const to = container.querySelector("#f-to").value;
      const limit = container.querySelector("#f-limit").value;
      if (actor) params.actor = actor;
      if (model) params.model = model;
      if (action) params.action = action;
      if (from) params.date_from = from;
      if (to) params.date_to = to;
      if (limit) params.limit = limit;
      try {
        const rows = await API.listAudit(params);
        if (rows.length === 0) {
          body.innerHTML = `<div class="empty">${t("audit.no_match")}</div>`;
          return;
        }
        body.innerHTML = `
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>${t("audit.time")}</th>
                  <th>${t("audit.actor")}</th>
                  <th>${t("audit.action")}</th>
                  <th>${t("audit.model")}</th>
                  <th class="num">${t("audit.record")}</th>
                </tr>
              </thead>
              <tbody>
                ${rows
                  .map((r) => `
                    <tr>
                      <td class="mono">${esc(fmtDateTime(r.timestamp))}</td>
                      <td class="mono">${esc(r.actor)}</td>
                      <td class="mono">${esc(r.action)}</td>
                      <td class="mono">${esc(r.model)}</td>
                      <td class="num mono">${r.record_id ?? ""}</td>
                    </tr>
                  `)
                  .join("")}
              </tbody>
            </table>
          </div>
        `;
      } catch (err) {
        toast(err.message, "error");
      }
    }

    for (const id of ["f-actor", "f-model", "f-action", "f-from", "f-to"]) {
      container.querySelector(`#${id}`).addEventListener("change", load);
    }
    container.querySelector("#f-refresh").addEventListener("click", load);

    await load();
  },
};
