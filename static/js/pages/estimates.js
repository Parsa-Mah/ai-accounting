// pages/estimates.js — quotes: list, create, convert to invoice.
import { API } from "../api.js";
import {
  fmtMoney,
  fmtDate,
  esc,
  statusBadge,
  toast,
  showFormError,
  clearFormError,
  todayISO,
} from "../ui.js";
import { createLineEditor } from "../doclines.js";

export default {
  async render(container) {
    const [customers, items] = await Promise.all([
      API.listCustomers(),
      API.listItems(),
    ]);
    const customerOptions = customers
      .map((c) => `<option value="${c.id}">${esc(c.name)}</option>`)
      .join("");

    container.innerHTML = `
      <div class="page-head">
        <div>
          <h1 class="page-title">Estimates</h1>
          <p class="page-sub">Quotes that post nothing until converted.</p>
        </div>
        <div class="btn-row">
          <button id="toggle-new" class="btn primary" type="button">New estimate</button>
        </div>
      </div>

      <div id="new-card" class="card" style="display:none">
        <h3>New estimate</h3>
        <form id="new-form" class="stack" novalidate>
          <div class="form-row c3">
            <label class="field"><span>Customer</span>
              <select name="customer_id" required>${customerOptions || '<option value="">No customers yet</option>'}</select>
            </label>
            <label class="field"><span>Date</span><input type="date" name="date" value="${todayISO()}" required /></label>
            <label class="field"><span>Tax rate (%)</span><input name="tax_rate" type="number" min="0" max="100" step="0.01" value="0" /></label>
          </div>

          <div class="line-editor">
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th style="min-width:180px">Item</th>
                    <th>Description</th>
                    <th>Qty</th>
                    <th>Unit price</th>
                    <th class="num">Amount</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody id="lines"></tbody>
              </table>
            </div>
            <div class="btn-row" style="margin-top:10px">
              <button type="button" id="add-line" class="btn">Add line</button>
              <span id="totals" class="muted"></span>
            </div>
          </div>

          <div class="btn-row">
            <button type="submit" class="btn primary">Create estimate</button>
            <button type="button" id="cancel-new" class="btn ghost">Cancel</button>
          </div>
        </form>
      </div>

      <div class="toolbar">
        <label class="field"><span>Customer</span>
          <select id="f-customer"><option value="">all</option>${customerOptions}</select>
        </label>
        <label class="field" style="flex-direction:row;align-items:center;gap:8px;padding-bottom:9px">
          <input type="checkbox" id="f-converted" style="width:auto" checked />
          <span style="font-weight:500">Include converted</span>
        </label>
        <button id="refresh" class="btn" type="button">Refresh</button>
      </div>

      <div id="estimates-table"></div>
    `;

    const newCard = container.querySelector("#new-card");
    const toggleBtn = container.querySelector("#toggle-new");
    toggleBtn.addEventListener("click", () => {
      const hidden = newCard.style.display === "none";
      newCard.style.display = hidden ? "" : "none";
      toggleBtn.textContent = hidden ? "Hide form" : "New estimate";
    });
    container.querySelector("#cancel-new").addEventListener("click", () => {
      newCard.style.display = "none";
      toggleBtn.textContent = "New estimate";
    });

    const totalsEl = container.querySelector("#totals");
    const editor = createLineEditor({
      tbody: container.querySelector("#lines"),
      addBtn: container.querySelector("#add-line"),
      items,
      onTotal: (subtotal) => {
        const rate = Number(container.querySelector('#new-form [name="tax_rate"]').value) || 0;
        const tax = Math.round(subtotal * rate / 100);
        totalsEl.innerHTML = `Subtotal <b>${fmtMoney(subtotal)}</b> &middot; Tax <b>${fmtMoney(tax)}</b> &middot; Total <b>${fmtMoney(subtotal + tax)}</b>`;
      },
    });
    container.querySelector('#new-form [name="tax_rate"]').addEventListener("input", editor.update);

    const form = container.querySelector("#new-form");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearFormError(form);
      const fd = new FormData(form);
      const lines = editor.lines();
      if (lines.length === 0) {
        showFormError(form, "Add at least one line.");
        return;
      }
      for (const l of lines) {
        if (Number.isNaN(l.unit_price_cents)) {
          showFormError(form, "A line has an invalid unit price.");
          return;
        }
        if (!l.item_id && !l.description) {
          showFormError(form, "Each line needs an item or a description.");
          return;
        }
      }
      const body = {
        customer_id: Number(fd.get("customer_id")),
        date: fd.get("date"),
        tax_rate: Number(fd.get("tax_rate")) || 0,
        lines,
      };
      try {
        await API.createEstimate(body);
        toast("Estimate created", "success");
        form.reset();
        form.querySelector('[name="date"]').value = todayISO();
        form.querySelector('[name="tax_rate"]').value = "0";
        container.querySelector("#lines").innerHTML = "";
        editor.addLine();
        newCard.style.display = "none";
        toggleBtn.textContent = "New estimate";
        await load();
      } catch (err) {
        showFormError(form, err.message);
      }
    });

    async function load() {
      const params = {};
      const customer = container.querySelector("#f-customer").value;
      params.include_converted = container.querySelector("#f-converted").checked;
      if (customer) params.customer_id = customer;
      const estimates = await API.listEstimates(params);
      renderTable(estimates);
    }

    function renderTable(estimates) {
      const el = container.querySelector("#estimates-table");
      if (estimates.length === 0) {
        el.innerHTML = `<div class="empty">No estimates yet.</div>`;
        return;
      }
      el.innerHTML = `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Customer</th>
                <th>Date</th>
                <th class="num">Subtotal</th>
                <th class="num">Tax</th>
                <th class="num">Total</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              ${estimates
                .map((est) => {
                  const canConvert = est.status !== "converted";
                  return `
                    <tr>
                      <td class="mono">${est.id}</td>
                      <td>${esc(est.customer_name)}</td>
                      <td class="mono">${esc(fmtDate(est.date))}</td>
                      <td class="num">${fmtMoney(est.subtotal_cents)}</td>
                      <td class="num">${fmtMoney(est.tax_cents)}</td>
                      <td class="num">${fmtMoney(est.total_cents)}</td>
                      <td>${statusBadge(est.status)}</td>
                      <td style="text-align:right">
                        ${canConvert ? `<button class="btn sm primary" data-convert="${est.id}">Convert to invoice</button>` : ""}
                      </td>
                    </tr>
                  `;
                })
                .join("")}
            </tbody>
          </table>
        </div>
      `;
      el.querySelectorAll("[data-convert]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const id = btn.dataset.convert;
          if (!window.confirm(`Convert estimate #${id} to an invoice? This posts it to the ledger.`)) return;
          try {
            await API.convertEstimate(id);
            toast("Converted to invoice", "success");
            await load();
          } catch (err) {
            toast(err.message, "error");
          }
        });
      });
    }

    container.querySelector("#f-customer").addEventListener("change", load);
    container.querySelector("#f-converted").addEventListener("change", load);
    container.querySelector("#refresh").addEventListener("click", load);

    await load();
  },
};
