// pages/budgets.js — planning: create budgets, actual-vs-budget report, manage.
import { API } from "../api.js";
import {
  fmtMoney,
  fmtDate,
  centsToDollars,
  dollarsToCents,
  esc,
  statusBadge,
  toast,
  showFormError,
  clearFormError,
} from "../ui.js";

export default {
  async render(container) {
    const accounts = await API.listAccounts();
    const accountOptions = accounts
      .map((a) => `<option value="${a.id}">${esc(a.number)} — ${esc(a.name)}</option>`)
      .join("");

    container.innerHTML = `
      <div class="page-head">
        <div>
          <h1 class="page-title">Budgets</h1>
          <p class="page-sub">Plan amounts per account and compare to actuals.</p>
        </div>
        <div class="btn-row">
          <button id="toggle-new" class="btn primary" type="button">New budget</button>
        </div>
      </div>

      <div id="new-card" class="card" style="display:none">
        <h3 id="form-title">New budget</h3>
        <form id="new-form" class="stack" novalidate>
          <input type="hidden" name="id" />
          <div class="form-row c2">
            <label class="field"><span>Account</span>
              <select name="account_id" id="budget-account" required>${accountOptions}</select>
            </label>
            <label class="field"><span>Budget amount</span><input name="amount" inputmode="decimal" required /></label>
          </div>
          <div class="form-row c3">
            <label class="field"><span>Start</span><input type="date" name="budget_start" required /></label>
            <label class="field"><span>End</span><input type="date" name="budget_end" required /></label>
            <label class="field"><span>Note</span><input name="note" /></label>
          </div>
          <div class="btn-row">
            <button type="submit" class="btn primary">Save budget</button>
            <button type="button" id="cancel-new" class="btn ghost">Cancel</button>
          </div>
        </form>
      </div>

      <div class="card">
        <h2>Budget report</h2>
        <div class="toolbar">
          <label class="field"><span>From</span><input type="date" id="r-start" /></label>
          <label class="field"><span>To</span><input type="date" id="r-end" /></label>
          <label class="field"><span>Account</span>
            <select id="r-account"><option value="">all</option>${accountOptions}</select>
          </label>
          <button id="r-refresh" class="btn" type="button">Run report</button>
        </div>
        <div id="report-body"><div class="empty">Pick a date range and run the report.</div></div>
      </div>

      <div class="card">
        <h2>All budgets</h2>
        <div id="budgets-list"></div>
      </div>
    `;

    const newCard = container.querySelector("#new-card");
    const toggleBtn = container.querySelector("#toggle-new");
    const form = container.querySelector("#new-form");
    let editingId = null;

    function resetForm() {
      form.reset();
      form.querySelector('[name="id"]').value = "";
      editingId = null;
      container.querySelector("#form-title").textContent = "New budget";
      container.querySelector("#budget-account").disabled = false;
    }

    toggleBtn.addEventListener("click", () => {
      const hidden = newCard.style.display === "none";
      if (hidden) resetForm();
      newCard.style.display = hidden ? "" : "none";
      toggleBtn.textContent = hidden ? "Hide form" : "New budget";
    });
    container.querySelector("#cancel-new").addEventListener("click", () => {
      newCard.style.display = "none";
      resetForm();
      toggleBtn.textContent = "New budget";
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearFormError(form);
      const fd = new FormData(form);
      const amount = dollarsToCents(fd.get("amount"));
      if (Number.isNaN(amount) || amount < 0) {
        showFormError(form, "Enter a valid budget amount.");
        return;
      }
      const start = fd.get("budget_start");
      const end = fd.get("budget_end");
      if (start > end) {
        showFormError(form, "Start must be on or before end.");
        return;
      }
      try {
        if (editingId) {
          await API.updateBudget(editingId, {
            budget_start: start,
            budget_end: end,
            budget_cents: amount,
            note: fd.get("note").trim() || null,
          });
          toast("Budget updated", "success");
        } else {
          await API.createBudget({
            account_id: Number(fd.get("account_id")),
            budget_start: start,
            budget_end: end,
            budget_cents: amount,
            note: fd.get("note").trim() || null,
          });
          toast("Budget created", "success");
        }
        newCard.style.display = "none";
        resetForm();
        toggleBtn.textContent = "New budget";
        await Promise.all([loadList(), loadReport()]);
      } catch (err) {
        showFormError(form, err.message);
      }
    });

    function openEdit(b) {
      editingId = b.id;
      form.querySelector('[name="id"]').value = b.id;
      form.querySelector("#budget-account").value = b.account_id;
      form.querySelector("#budget-account").disabled = true;
      form.querySelector('[name="amount"]').value = centsToDollars(b.budget_cents);
      form.querySelector('[name="budget_start"]').value = b.budget_start;
      form.querySelector('[name="budget_end"]').value = b.budget_end;
      form.querySelector('[name="note"]').value = b.note || "";
      container.querySelector("#form-title").textContent = `Edit budget #${b.id}`;
      newCard.style.display = "";
      toggleBtn.textContent = "Hide form";
      newCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    // ----- Report -----
    async function loadReport() {
      const start = container.querySelector("#r-start").value;
      const end = container.querySelector("#r-end").value;
      const el = container.querySelector("#report-body");
      if (!start || !end) {
        el.innerHTML = `<div class="empty">Pick a start and end date.</div>`;
        return;
      }
      const params = { start, end };
      const account = container.querySelector("#r-account").value;
      if (account) params.account_id = account;
      const report = await API.budgetReport(params);
      if (report.rows.length === 0) {
        el.innerHTML = `<div class="empty">No budgets fully contained in ${esc(fmtDate(start))} → ${esc(fmtDate(end))}.</div>`;
        return;
      }
      el.innerHTML = `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Account</th>
                <th>Period</th>
                <th class="num">Budget</th>
                <th class="num">Actual</th>
                <th class="num">Variance</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              ${report.rows
                .map((r) => `
                  <tr>
                    <td><span class="mono faint">${esc(r.account_number)}</span> ${esc(r.account_name)}</td>
                    <td class="mono">${esc(fmtDate(r.budget_start))} → ${esc(fmtDate(r.budget_end))}</td>
                    <td class="num">${fmtMoney(r.budget_cents)}</td>
                    <td class="num">${fmtMoney(r.actual_cents)}</td>
                    <td class="num" style="color:${r.variance_cents < 0 ? "var(--danger)" : "var(--success)"}">${fmtMoney(r.variance_cents)}</td>
                    <td>${statusBadge(r.within_budget ? "within budget" : "over budget")}</td>
                  </tr>
                `)
                .join("")}
              <tr class="total">
                <td colspan="2">Totals</td>
                <td class="num">${fmtMoney(report.totals.budget_cents)}</td>
                <td class="num">${fmtMoney(report.totals.actual_cents)}</td>
                <td class="num">${fmtMoney(report.totals.variance_cents)}</td>
                <td></td>
              </tr>
            </tbody>
          </table>
        </div>
      `;
    }

    // ----- List -----
    async function loadList() {
      const budgets = await API.listBudgets();
      const el = container.querySelector("#budgets-list");
      if (budgets.length === 0) {
        el.innerHTML = `<div class="empty">No budgets yet.</div>`;
        return;
      }
      el.innerHTML = `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Account</th>
                <th>Period</th>
                <th class="num">Budget</th>
                <th>Note</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              ${budgets
                .map((b) => `
                  <tr>
                    <td class="mono">${b.id}</td>
                    <td><span class="mono faint">${esc(b.account_number)}</span> ${esc(b.account_name)}</td>
                    <td class="mono">${esc(fmtDate(b.budget_start))} → ${esc(fmtDate(b.budget_end))}</td>
                    <td class="num">${fmtMoney(b.budget_cents)}</td>
                    <td class="muted">${esc(b.note || "")}</td>
                    <td style="text-align:right;white-space:nowrap">
                      <button class="btn sm" data-edit="${b.id}">Edit</button>
                      <button class="btn sm danger" data-del="${b.id}">Delete</button>
                    </td>
                  </tr>
                `)
                .join("")}
            </tbody>
          </table>
        </div>
      `;
      el.querySelectorAll("[data-edit]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const b = budgets.find((x) => x.id === Number(btn.dataset.edit));
          if (b) openEdit(b);
        });
      });
      el.querySelectorAll("[data-del]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const id = btn.dataset.del;
          if (!window.confirm(`Delete budget #${id}?`)) return;
          try {
            await API.deleteBudget(id);
            toast("Budget deleted", "success");
            await Promise.all([loadList(), loadReport()]);
          } catch (err) {
            toast(err.message, "error");
          }
        });
      });
    }

    container.querySelector("#r-start").addEventListener("change", loadReport);
    container.querySelector("#r-end").addEventListener("change", loadReport);
    container.querySelector("#r-account").addEventListener("change", loadReport);
    container.querySelector("#r-refresh").addEventListener("click", loadReport);

    await loadList();
  },
};
