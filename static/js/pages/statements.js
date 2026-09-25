// pages/statements.js — income statement and balance sheet.
import { API } from "../api.js";
import { fmtMoney, fmtDate, esc } from "../ui.js";

function lineRows(lines) {
  if (lines.length === 0) return `<tr><td class="muted" colspan="2">—</td></tr>`;
  return lines
    .map(
      (l) => `
        <tr>
          <td>${l.number ? `<span class="mono faint">${esc(l.number)}</span> ` : ""}${esc(l.name)}</td>
          <td class="num">${fmtMoney(l.amount)}</td>
        </tr>
      `,
    )
    .join("");
}

export default {
  async render(container) {
    container.innerHTML = `
      <div class="page-head">
        <div>
          <h1 class="page-title">Statements</h1>
          <p class="page-sub">Financial statements derived from the ledger.</p>
        </div>
      </div>

      <div class="card">
        <h2>Income statement</h2>
        <div class="toolbar">
          <label class="field"><span>From</span><input type="date" id="is-from" /></label>
          <label class="field"><span>To</span><input type="date" id="is-to" /></label>
          <button id="is-refresh" class="btn" type="button">Refresh</button>
        </div>
        <div id="is-body"></div>
      </div>

      <div class="card">
        <h2>Balance sheet</h2>
        <div class="toolbar">
          <label class="field"><span>As of</span><input type="date" id="bs-asof" /></label>
          <button id="bs-refresh" class="btn" type="button">Refresh</button>
        </div>
        <div id="bs-body"></div>
      </div>
    `;

    async function loadIS() {
      const params = {};
      const from = container.querySelector("#is-from").value;
      const to = container.querySelector("#is-to").value;
      if (from) params.date_from = from;
      if (to) params.date_to = to;
      const is = await API.incomeStatement(params);
      const range =
        is.date_from || is.date_to
          ? `${fmtDate(is.date_from) || "…"} → ${fmtDate(is.date_to) || "…"}`
          : "All time";
      const ni = is.net_income;
      container.querySelector("#is-body").innerHTML = `
        <div class="muted" style="margin-bottom:10px">${esc(range)}</div>
        <div class="table-wrap">
          <table>
            <tbody>
              <tr class="total"><td>Revenue</td><td></td></tr>
              ${lineRows(is.revenue)}
              <tr class="total"><td>Total revenue</td><td class="num">${fmtMoney(is.total_revenue)}</td></tr>
              <tr class="total"><td>Expenses</td><td></td></tr>
              ${lineRows(is.expenses)}
              <tr class="total"><td>Total expenses</td><td class="num">${fmtMoney(is.total_expenses)}</td></tr>
              <tr class="total">
                <td>Net income</td>
                <td class="num" style="color:${ni < 0 ? "var(--danger)" : "var(--success)"}">${fmtMoney(ni)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      `;
    }

    async function loadBS() {
      const params = {};
      const asof = container.querySelector("#bs-asof").value;
      if (asof) params.as_of = asof;
      const bs = await API.balanceSheet(params);
      const asOf = bs.as_of ? fmtDate(bs.as_of) : "Current";
      container.querySelector("#bs-body").innerHTML = `
        <div class="muted" style="margin-bottom:10px">
          As of ${esc(asOf)}
          ${bs.balanced ? '<span class="badge success">A = L + E</span>' : '<span class="badge danger">out of balance</span>'}
        </div>
        <div class="table-wrap">
          <table>
            <tbody>
              <tr class="total"><td>Assets</td><td></td></tr>
              ${lineRows(bs.assets)}
              <tr class="total"><td>Total assets</td><td class="num">${fmtMoney(bs.total_assets)}</td></tr>
              <tr class="total"><td>Liabilities</td><td></td></tr>
              ${lineRows(bs.liabilities)}
              <tr class="total"><td>Total liabilities</td><td class="num">${fmtMoney(bs.total_liabilities)}</td></tr>
              <tr class="total"><td>Equity</td><td></td></tr>
              ${lineRows(bs.equity)}
              <tr class="total"><td>Total equity</td><td class="num">${fmtMoney(bs.total_equity)}</td></tr>
              <tr class="total"><td>Liabilities + equity</td><td class="num">${fmtMoney(bs.total_liabilities + bs.total_equity)}</td></tr>
            </tbody>
          </table>
        </div>
      `;
    }

    container.querySelector("#is-from").addEventListener("change", loadIS);
    container.querySelector("#is-to").addEventListener("change", loadIS);
    container.querySelector("#is-refresh").addEventListener("click", loadIS);
    container.querySelector("#bs-asof").addEventListener("change", loadBS);
    container.querySelector("#bs-refresh").addEventListener("click", loadBS);

    await Promise.all([loadIS(), loadBS()]);
  },
};
