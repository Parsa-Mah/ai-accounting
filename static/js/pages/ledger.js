// pages/ledger.js — general ledger (per account) and trial balance.
import { API } from "../api.js";
import { fmtMoney, fmtDate, esc, statusBadge } from "../ui.js";
import { t } from "../i18n.js";

export default {
  async render(container) {
    const accounts = await API.listAccounts({ include_inactive: true });
    const accountOptions = accounts
      .map((a) => `<option value="${a.id}">${esc(a.number)} — ${esc(a.name)}</option>`)
      .join("");

    container.innerHTML = `
      <div class="page-head">
        <div>
          <h1 class="page-title">${t("nav.ledger")}</h1>
          <p class="page-sub">${t("ledger.subtitle")}</p>
        </div>
      </div>

      <div class="card">
        <h2>${t("ledger.general")}</h2>
        <div class="toolbar">
          <label class="field" style="min-width:240px"><span>${t("common.account")}</span>
            <select id="gl-account">${accountOptions}</select>
          </label>
          <label class="field"><span>${t("common.from")}</span><input type="date" id="gl-from" /></label>
          <label class="field"><span>${t("common.to")}</span><input type="date" id="gl-to" /></label>
          <label class="field" style="flex-direction:row;align-items:center;gap:8px;padding-bottom:9px">
            <input type="checkbox" id="gl-voided" style="width:auto" checked />
            <span style="font-weight:500">${t("common.include_voided")}</span>
          </label>
          <button id="gl-refresh" class="btn" type="button">${t("common.refresh")}</button>
        </div>
        <div id="gl-summary" class="muted" style="margin-bottom:10px"></div>
        <div id="gl-table"></div>
      </div>

      <div class="card">
        <h2>${t("ledger.trial_balance")}</h2>
        <div class="toolbar">
          <label class="field"><span>${t("common.as_of")}</span><input type="date" id="tb-asof" /></label>
          <button id="tb-refresh" class="btn" type="button">${t("common.refresh")}</button>
        </div>
        <div id="tb-table"></div>
      </div>
    `;

    // ----- General ledger -----
    async function loadGL() {
      const accountId = Number(container.querySelector("#gl-account").value);
      const params = {};
      const from = container.querySelector("#gl-from").value;
      const to = container.querySelector("#gl-to").value;
      params.include_voided = container.querySelector("#gl-voided").checked;
      if (from) params.date_from = from;
      if (to) params.date_to = to;
      const gl = await API.generalLedger(accountId, params);
      renderGL(gl);
    }

    function renderGL(gl) {
      const summary = container.querySelector("#gl-summary");
      summary.innerHTML = t("ledger.summary", {
        account: `${esc(gl.account_number)} ${esc(gl.account_name)}`,
        opening: fmtMoney(gl.opening_balance),
        closing: fmtMoney(gl.closing_balance),
      });
      const el = container.querySelector("#gl-table");
      if (gl.lines.length === 0) {
        el.innerHTML = `<div class="empty">${t("ledger.no_activity")}</div>`;
        return;
      }
      el.innerHTML = `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>${t("common.date")}</th>
                <th>${t("common.entry")}</th>
                <th>${t("common.description")}</th>
                <th class="num">${t("common.debit")}</th>
                <th class="num">${t("common.credit")}</th>
                <th class="num">${t("common.balance")}</th>
                <th>${t("common.cleared")}</th>
              </tr>
            </thead>
            <tbody>
              ${gl.lines
                .map((l) => `
                  <tr class="${l.is_voided ? "voided" : ""}">
                    <td class="mono">${esc(fmtDate(l.date))}</td>
                    <td class="mono">#${l.entry_id}</td>
                    <td>${esc(l.entry_description)}${l.line_description ? ` <span class="faint">— ${esc(l.line_description)}</span>` : ""}</td>
                    <td class="num">${l.debit ? fmtMoney(l.debit) : ""}</td>
                    <td class="num">${l.credit ? fmtMoney(l.credit) : ""}</td>
                    <td class="num">${fmtMoney(l.balance)}</td>
                    <td>${l.cleared ? statusBadge("active") : '<span class="faint">—</span>'}</td>
                  </tr>
                `)
                .join("")}
            </tbody>
          </table>
        </div>
      `;
    }

    // ----- Trial balance -----
    async function loadTB() {
      const params = {};
      const asof = container.querySelector("#tb-asof").value;
      if (asof) params.as_of = asof;
      const tb = await API.trialBalance(params);
      renderTB(tb);
    }

    function renderTB(tb) {
      const el = container.querySelector("#tb-table");
      if (tb.rows.length === 0) {
        el.innerHTML = `<div class="empty">${t("ledger.no_balances")}</div>`;
        return;
      }
      el.innerHTML = `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>${t("common.number")}</th>
                <th>${t("common.name")}</th>
                <th>${t("common.type")}</th>
                <th class="num">${t("common.debit")}</th>
                <th class="num">${t("common.credit")}</th>
              </tr>
            </thead>
            <tbody>
              ${tb.rows
                .map((r) => `
                  <tr>
                    <td class="mono">${esc(r.number)}</td>
                    <td>${esc(r.name)}</td>
                    <td><span class="badge">${esc(r.type)}</span></td>
                    <td class="num">${r.debit ? fmtMoney(r.debit) : ""}</td>
                    <td class="num">${r.credit ? fmtMoney(r.credit) : ""}</td>
                  </tr>
                `)
                .join("")}
              <tr class="total">
                <td colspan="3">${t("common.totals")} ${tb.balanced ? `<span class="badge success">${t("ledger.tb_balanced")}</span>` : `<span class="badge danger">${t("ledger.tb_out_of_balance")}</span>`}</td>
                <td class="num">${fmtMoney(tb.totals.debit)}</td>
                <td class="num">${fmtMoney(tb.totals.credit)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      `;
    }

    container.querySelector("#gl-account").addEventListener("change", loadGL);
    container.querySelector("#gl-from").addEventListener("change", loadGL);
    container.querySelector("#gl-to").addEventListener("change", loadGL);
    container.querySelector("#gl-voided").addEventListener("change", loadGL);
    container.querySelector("#gl-refresh").addEventListener("click", loadGL);
    container.querySelector("#tb-asof").addEventListener("change", loadTB);
    container.querySelector("#tb-refresh").addEventListener("click", loadTB);

    await Promise.all([loadGL(), loadTB()]);
  },
};
