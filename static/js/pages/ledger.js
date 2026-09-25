// pages/ledger.js — general ledger (per account) and trial balance.
import { API } from "../api.js";
import { fmtMoney, fmtDate, esc, statusBadge } from "../ui.js";

export default {
  async render(container) {
    const accounts = await API.listAccounts({ include_inactive: true });
    const accountOptions = accounts
      .map((a) => `<option value="${a.id}">${esc(a.number)} — ${esc(a.name)}</option>`)
      .join("");

    container.innerHTML = `
      <div class="page-head">
        <div>
          <h1 class="page-title">Ledger</h1>
          <p class="page-sub">Account activity and the trial balance.</p>
        </div>
      </div>

      <div class="card">
        <h2>General ledger</h2>
        <div class="toolbar">
          <label class="field" style="min-width:240px"><span>Account</span>
            <select id="gl-account">${accountOptions}</select>
          </label>
          <label class="field"><span>From</span><input type="date" id="gl-from" /></label>
          <label class="field"><span>To</span><input type="date" id="gl-to" /></label>
          <label class="field" style="flex-direction:row;align-items:center;gap:8px;padding-bottom:9px">
            <input type="checkbox" id="gl-voided" style="width:auto" checked />
            <span style="font-weight:500">Include voided</span>
          </label>
          <button id="gl-refresh" class="btn" type="button">Refresh</button>
        </div>
        <div id="gl-summary" class="muted" style="margin-bottom:10px"></div>
        <div id="gl-table"></div>
      </div>

      <div class="card">
        <h2>Trial balance</h2>
        <div class="toolbar">
          <label class="field"><span>As of</span><input type="date" id="tb-asof" /></label>
          <button id="tb-refresh" class="btn" type="button">Refresh</button>
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
      summary.innerHTML = `
        <b>${esc(gl.account_number)} ${esc(gl.account_name)}</b>
        &middot; Opening <b>${fmtMoney(gl.opening_balance)}</b>
        &middot; Closing <b>${fmtMoney(gl.closing_balance)}</b>
      `;
      const el = container.querySelector("#gl-table");
      if (gl.lines.length === 0) {
        el.innerHTML = `<div class="empty">No activity for this account in the selected range.</div>`;
        return;
      }
      el.innerHTML = `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Entry</th>
                <th>Description</th>
                <th class="num">Debit</th>
                <th class="num">Credit</th>
                <th class="num">Balance</th>
                <th>Cleared</th>
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
        el.innerHTML = `<div class="empty">No balances yet.</div>`;
        return;
      }
      el.innerHTML = `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Number</th>
                <th>Name</th>
                <th>Type</th>
                <th class="num">Debit</th>
                <th class="num">Credit</th>
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
                <td colspan="3">Totals ${tb.balanced ? '<span class="badge success">balanced</span>' : '<span class="badge danger">out of balance</span>'}</td>
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
