// pages/statements.js — income statement and balance sheet.
import { API } from "../api.js";
import { fmtMoney, fmtDate, esc } from "../ui.js";
import { t } from "../i18n.js";

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
          <h1 class="page-title">${t("nav.statements")}</h1>
          <p class="page-sub">${t("statements.subtitle")}</p>
        </div>
      </div>

      <div class="card">
        <h2>${t("statements.income")}</h2>
        <div class="toolbar">
          <label class="field"><span>${t("common.from")}</span><input type="date" id="is-from" /></label>
          <label class="field"><span>${t("common.to")}</span><input type="date" id="is-to" /></label>
          <button id="is-refresh" class="btn" type="button">${t("common.refresh")}</button>
        </div>
        <div id="is-body"></div>
      </div>

      <div class="card">
        <h2>${t("statements.balance_sheet")}</h2>
        <div class="toolbar">
          <label class="field"><span>${t("common.as_of")}</span><input type="date" id="bs-asof" /></label>
          <button id="bs-refresh" class="btn" type="button">${t("common.refresh")}</button>
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
          : t("common.all_time");
      const ni = is.net_income;
      container.querySelector("#is-body").innerHTML = `
        <div class="muted" style="margin-bottom:10px">${esc(range)}</div>
        <div class="table-wrap">
          <table>
            <tbody>
              <tr class="total"><td>${t("statements.revenue")}</td><td></td></tr>
              ${lineRows(is.revenue)}
              <tr class="total"><td>${t("statements.total_revenue")}</td><td class="num">${fmtMoney(is.total_revenue)}</td></tr>
              <tr class="total"><td>${t("statements.expenses")}</td><td></td></tr>
              ${lineRows(is.expenses)}
              <tr class="total"><td>${t("statements.total_expenses")}</td><td class="num">${fmtMoney(is.total_expenses)}</td></tr>
              <tr class="total">
                <td>${t("statements.net_income")}</td>
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
      const asOf = bs.as_of ? fmtDate(bs.as_of) : t("statements.current");
      container.querySelector("#bs-body").innerHTML = `
        <div class="muted" style="margin-bottom:10px">
          ${t("statements.as_of", { date: esc(asOf) })}
          ${bs.balanced ? `<span class="badge success">${t("statements.badge_balanced")}</span>` : `<span class="badge danger">${t("statements.badge_out_of_balance")}</span>`}
        </div>
        <div class="table-wrap">
          <table>
            <tbody>
              <tr class="total"><td>${t("statements.assets")}</td><td></td></tr>
              ${lineRows(bs.assets)}
              <tr class="total"><td>${t("statements.total_assets")}</td><td class="num">${fmtMoney(bs.total_assets)}</td></tr>
              <tr class="total"><td>${t("statements.liabilities")}</td><td></td></tr>
              ${lineRows(bs.liabilities)}
              <tr class="total"><td>${t("statements.total_liabilities")}</td><td class="num">${fmtMoney(bs.total_liabilities)}</td></tr>
              <tr class="total"><td>${t("statements.equity")}</td><td></td></tr>
              ${lineRows(bs.equity)}
              <tr class="total"><td>${t("statements.total_equity")}</td><td class="num">${fmtMoney(bs.total_equity)}</td></tr>
              <tr class="total"><td>${t("statements.liabilities_plus_equity")}</td><td class="num">${fmtMoney(bs.total_liabilities + bs.total_equity)}</td></tr>
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
