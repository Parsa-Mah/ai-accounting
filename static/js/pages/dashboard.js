// pages/dashboard.js — overview: key balances, period P&L, recent activity.
import { API } from "../api.js";
import { fmtMoney, fmtDate, esc, statusBadge } from "../ui.js";
import { t } from "../i18n.js";

function netByNumber(rows, number) {
  const row = rows.find((r) => r.number === number);
  if (!row) return 0;
  return row.debit - row.credit; // debit-positive
}

export default {
  async render(container) {
    container.innerHTML = `
      <div class="page-head">
        <div>
          <h1 class="page-title">${t("nav.dashboard")}</h1>
          <p class="page-sub">${t("dashboard.subtitle")}</p>
        </div>
      </div>
      <div id="dash-cards" class="grid cols-4">
        <div class="empty">${t("common.loading")}</div>
      </div>
      <div class="card">
        <h2>${t("dashboard.recent")}</h2>
        <div id="dash-recent"></div>
      </div>
    `;

    const [tb, income, entries] = await Promise.all([
      API.trialBalance(),
      API.incomeStatement(),
      API.listJournal({ include_voided: false }),
    ]);

    const cash = netByNumber(tb.rows, "1000");
    const ar = netByNumber(tb.rows, "1100");
    const ap = -netByNumber(tb.rows, "2000"); // AP is credit-normal
    const netIncome = income.net_income;

    const cards = [
      { label: t("dashboard.cash"), value: cash },
      { label: t("dashboard.ar"), value: ar },
      { label: t("dashboard.ap"), value: ap },
      { label: t("dashboard.net_income"), value: netIncome },
    ];

    const cardsEl = container.querySelector("#dash-cards");
    cardsEl.innerHTML = cards
      .map((c) => {
        const cls = c.value < 0 ? "neg" : c.value > 0 ? "pos" : "";
        return `
          <div class="stat">
            <div class="label">${esc(c.label)}</div>
            <div class="value ${cls}">${fmtMoney(c.value)}</div>
          </div>
        `;
      })
      .join("");

    const recentEl = container.querySelector("#dash-recent");
    const recent = entries.slice(0, 10);
    if (recent.length === 0) {
      recentEl.innerHTML = `<div class="empty">${t("dashboard.no_entries")}</div>`;
      return;
    }
    recentEl.innerHTML = `
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>${t("common.date")}</th>
              <th>${t("common.description")}</th>
              <th>${t("common.source")}</th>
              <th class="num">${t("common.amount")}</th>
              <th>${t("common.status")}</th>
            </tr>
          </thead>
          <tbody>
            ${recent
              .map((e) => {
                const total = e.lines.reduce((s, l) => s + l.debit, 0);
                return `
                  <tr class="${e.is_voided ? "voided" : ""}">
                    <td class="mono">${esc(fmtDate(e.date))}</td>
                    <td>${esc(e.description)}</td>
                    <td><span class="badge">${esc(e.source_type)}</span></td>
                    <td class="num">${fmtMoney(total)}</td>
                    <td>${e.is_voided ? statusBadge("void") : statusBadge("active")}</td>
                  </tr>
                `;
              })
              .join("")}
          </tbody>
        </table>
      </div>
    `;
  },
};
