// pages/reconciliation.js — bank reconciliation: pick a bank account, clear lines, match statement.
import { API } from "../api.js";
import {
  fmtMoney,
  fmtDate,
  dollarsToCents,
  esc,
  statusBadge,
  toast,
  showFormError,
  clearFormError,
  todayISO,
} from "../ui.js";

export default {
  async render(container) {
    const bankAccounts = await API.bankAccounts();
    const accountOptions = bankAccounts
      .map(
        (a) =>
          `<option value="${a.id}">${esc(a.number)} — ${esc(a.name)} (${esc(a.bank_kind)})</option>`,
      )
      .join("");

    container.innerHTML = `
      <div class="page-head">
        <div>
          <h1 class="page-title">Reconciliation</h1>
          <p class="page-sub">Match bank statements to cleared journal lines.</p>
        </div>
      </div>

      ${bankAccounts.length === 0 ? '<div class="card"><div class="empty">No bank accounts yet. Create an account with a bank kind (e.g. checking) under Accounts.</div></div>' : ""}

      <div class="card">
        <h2>New reconciliation</h2>
        <form id="recon-form" class="stack" novalidate>
          <div class="form-row c3">
            <label class="field"><span>Bank account</span>
              <select name="account_id" id="recon-account" required>${accountOptions}</select>
            </label>
            <label class="field"><span>Statement date</span><input type="date" name="statement_date" value="${todayISO()}" required /></label>
            <label class="field"><span>Statement balance</span><input name="statement_balance" inputmode="decimal" required /></label>
          </div>
          <label class="field"><span>Note (optional)</span><input name="note" /></label>

          <div>
            <div class="muted" style="margin-bottom:8px">Select the lines to clear against this statement:</div>
            <div id="lines-body"><div class="empty">Choose a bank account to load its register.</div></div>
          </div>

          <div class="btn-row">
            <button type="submit" class="btn primary">Create reconciliation</button>
          </div>
        </form>
      </div>

      <div class="card">
        <h2>Reconciliations</h2>
        <div class="toolbar">
          <label class="field"><span>Account</span>
            <select id="f-account"><option value="">all</option>${accountOptions}</select>
          </label>
          <button id="refresh" class="btn" type="button">Refresh</button>
        </div>
        <div id="recons-list"></div>
      </div>
    `;

    const form = container.querySelector("#recon-form");
    const linesBody = container.querySelector("#lines-body");

    // Load the selected bank account's register; show uncleared lines as checkboxes.
    async function loadLines() {
      const accountId = Number(form.querySelector("#recon-account").value);
      if (!accountId) {
        linesBody.innerHTML = `<div class="empty">Choose a bank account to load its register.</div>`;
        return;
      }
      const gl = await API.generalLedger(accountId);
      const uncleared = gl.lines.filter((l) => !l.cleared);
      if (uncleared.length === 0) {
        linesBody.innerHTML = `<div class="empty">No uncleared lines for this account.</div>`;
        return;
      }
      linesBody.innerHTML = `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th style="width:40px"></th>
                <th>Date</th>
                <th>Description</th>
                <th class="num">Debit</th>
                <th class="num">Credit</th>
              </tr>
            </thead>
            <tbody>
              ${uncleared
                .map((l) => `
                  <tr>
                    <td><input type="checkbox" class="line-check" data-line-id="${l.line_id}" /></td>
                    <td class="mono">${esc(fmtDate(l.date))}</td>
                    <td>${esc(l.entry_description)}${l.line_description ? ` <span class="faint">— ${esc(l.line_description)}</span>` : ""}</td>
                    <td class="num">${l.debit ? fmtMoney(l.debit) : ""}</td>
                    <td class="num">${l.credit ? fmtMoney(l.credit) : ""}</td>
                  </tr>
                `)
                .join("")}
            </tbody>
          </table>
        </div>
      `;
    }

    form.querySelector("#recon-account").addEventListener("change", loadLines);

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearFormError(form);
      const fd = new FormData(form);
      const lineIds = Array.from(linesBody.querySelectorAll(".line-check:checked")).map(
        (c) => Number(c.dataset.lineId),
      );
      if (lineIds.length === 0) {
        showFormError(form, "Select at least one line to clear.");
        return;
      }
      const balance = dollarsToCents(fd.get("statement_balance"));
      if (Number.isNaN(balance)) {
        showFormError(form, "Enter a valid statement balance.");
        return;
      }
      const body = {
        account_id: Number(fd.get("account_id")),
        statement_date: fd.get("statement_date"),
        statement_balance_cents: balance,
        line_ids: lineIds,
        note: fd.get("note").trim() || null,
      };
      try {
        const recon = await API.createReconciliation(body);
        const msg = recon.is_balanced
          ? "Reconciliation created — balanced"
          : `Reconciliation created — difference ${fmtMoney(recon.difference_cents)}`;
        toast(msg, recon.is_balanced ? "success" : "info");
        form.querySelector('[name="statement_balance"]').value = "";
        form.querySelector('[name="note"]').value = "";
        await Promise.all([loadLines(), loadList()]);
      } catch (err) {
        showFormError(form, err.message);
      }
    });

    async function loadList() {
      const params = {};
      const account = container.querySelector("#f-account").value;
      if (account) params.account_id = account;
      const recons = await API.listReconciliations(params);
      const el = container.querySelector("#recons-list");
      if (recons.length === 0) {
        el.innerHTML = `<div class="empty">No reconciliations yet.</div>`;
        return;
      }
      el.innerHTML = `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Account</th>
                <th>Statement date</th>
                <th class="num">Statement</th>
                <th class="num">Opening</th>
                <th class="num">Cleared</th>
                <th class="num">Difference</th>
                <th>Lines</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              ${recons
                .map((r) => `
                  <tr>
                    <td class="mono">${r.id}</td>
                    <td><span class="mono faint">${esc(r.account_number)}</span> ${esc(r.account_name)}</td>
                    <td class="mono">${esc(fmtDate(r.statement_date))}</td>
                    <td class="num">${fmtMoney(r.statement_balance_cents)}</td>
                    <td class="num">${fmtMoney(r.opening_balance_cents)}</td>
                    <td class="num">${fmtMoney(r.cleared_total_cents)}</td>
                    <td class="num" style="color:${r.difference_cents === 0 ? "var(--success)" : "var(--warning)"}">${fmtMoney(r.difference_cents)}</td>
                    <td class="num">${r.line_count}</td>
                    <td>${r.is_balanced ? statusBadge("balanced") : statusBadge("outstanding")}</td>
                    <td style="text-align:right"><button class="btn sm danger" data-del="${r.id}">Delete</button></td>
                  </tr>
                `)
                .join("")}
            </tbody>
          </table>
        </div>
      `;
      el.querySelectorAll("[data-del]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const id = btn.dataset.del;
          if (!window.confirm(`Delete reconciliation #${id}? Its cleared lines will be un-cleared.`)) return;
          try {
            await API.deleteReconciliation(id);
            toast("Reconciliation deleted", "success");
            await Promise.all([loadList(), loadLines()]);
          } catch (err) {
            toast(err.message, "error");
          }
        });
      });
    }

    container.querySelector("#f-account").addEventListener("change", loadList);
    container.querySelector("#refresh").addEventListener("click", loadList);

    await loadList();
    if (bankAccounts.length > 0) await loadLines();
  },
};
