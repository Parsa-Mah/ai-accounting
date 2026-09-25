// pages/invoices.js — accounts receivable: list, create, record payment, void.
import { API } from "../api.js";
import {
  fmtMoney,
  fmtDate,
  centsToDollars,
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
          <h1 class="page-title">Invoices</h1>
          <p class="page-sub">Bill customers (accounts receivable).</p>
        </div>
        <div class="btn-row">
          <button id="toggle-new" class="btn primary" type="button">New invoice</button>
        </div>
      </div>

      <div id="new-card" class="card" style="display:none">
        <h3>New invoice</h3>
        <form id="new-form" class="stack" novalidate>
          <div class="form-row c3">
            <label class="field"><span>Customer</span>
              <select name="customer_id" required>${customerOptions || '<option value="">No customers yet</option>'}</select>
            </label>
            <label class="field"><span>Date</span><input type="date" name="date" value="${todayISO()}" required /></label>
            <label class="field"><span>Due date</span><input type="date" name="due_date" /></label>
          </div>
          <div class="form-row c2">
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
            <button type="submit" class="btn primary">Create invoice</button>
            <button type="button" id="cancel-new" class="btn ghost">Cancel</button>
          </div>
        </form>
      </div>

      <div id="pay-card" class="card" style="display:none">
        <h3>Record payment</h3>
        <form id="pay-form" class="stack" novalidate>
          <div class="form-row c3">
            <label class="field"><span>Amount</span><input name="amount" inputmode="decimal" required /></label>
            <label class="field"><span>Date</span><input type="date" name="date" value="${todayISO()}" /></label>
            <label class="field"><span>Note</span><input name="note" /></label>
          </div>
          <div class="btn-row">
            <button type="submit" class="btn primary">Record payment</button>
            <button type="button" id="cancel-pay" class="btn ghost">Cancel</button>
          </div>
        </form>
      </div>

      <div class="toolbar">
        <label class="field"><span>Customer</span>
          <select id="f-customer"><option value="">all</option>${customerOptions}</select>
        </label>
        <label class="field" style="flex-direction:row;align-items:center;gap:8px;padding-bottom:9px">
          <input type="checkbox" id="f-voided" style="width:auto" checked />
          <span style="font-weight:500">Include voided</span>
        </label>
        <button id="refresh" class="btn" type="button">Refresh</button>
      </div>

      <div id="invoices-table"></div>
    `;

    // ----- New invoice -----
    const newCard = container.querySelector("#new-card");
    const toggleBtn = container.querySelector("#toggle-new");
    toggleBtn.addEventListener("click", () => {
      const hidden = newCard.style.display === "none";
      newCard.style.display = hidden ? "" : "none";
      toggleBtn.textContent = hidden ? "Hide form" : "New invoice";
    });
    container.querySelector("#cancel-new").addEventListener("click", () => {
      newCard.style.display = "none";
      toggleBtn.textContent = "New invoice";
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
        due_date: fd.get("due_date") || null,
        tax_rate: Number(fd.get("tax_rate")) || 0,
        lines,
      };
      try {
        await API.createInvoice(body);
        toast("Invoice created", "success");
        form.reset();
        form.querySelector('[name="date"]').value = todayISO();
        form.querySelector('[name="tax_rate"]').value = "0";
        container.querySelector("#lines").innerHTML = "";
        editor.addLine();
        newCard.style.display = "none";
        toggleBtn.textContent = "New invoice";
        await load();
      } catch (err) {
        showFormError(form, err.message);
      }
    });

    // ----- Payment -----
    const payCard = container.querySelector("#pay-card");
    const payForm = container.querySelector("#pay-form");
    let payTarget = null;
    container.querySelector("#cancel-pay").addEventListener("click", () => {
      payCard.style.display = "none";
      payTarget = null;
    });
    payForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearFormError(payForm);
      const fd = new FormData(payForm);
      const amount = Math.round(Number(fd.get("amount").replace(/[$,\s]/g, "")) * 100);
      if (!amount || amount <= 0) {
        showFormError(payForm, "Enter a valid amount.");
        return;
      }
      try {
        await API.payInvoice(payTarget.id, {
          amount_cents: amount,
          date: fd.get("date") || null,
          note: fd.get("note").trim() || null,
        });
        toast("Payment recorded", "success");
        payCard.style.display = "none";
        payTarget = null;
        await load();
      } catch (err) {
        showFormError(payForm, err.message);
      }
    });

    function openPay(invoice) {
      payTarget = invoice;
      const remaining = invoice.total_cents - invoice.paid_cents;
      payForm.querySelector('[name="amount"]').value = centsToDollars(remaining);
      payForm.querySelector('[name="date"]').value = todayISO();
      payForm.querySelector('[name="note"]').value = "";
      payCard.style.display = "";
      payCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    // ----- List -----
    async function load() {
      const params = {};
      const customer = container.querySelector("#f-customer").value;
      params.include_voided = container.querySelector("#f-voided").checked;
      if (customer) params.customer_id = customer;
      const invoices = await API.listInvoices(params);
      renderTable(invoices);
    }

    function renderTable(invoices) {
      const el = container.querySelector("#invoices-table");
      if (invoices.length === 0) {
        el.innerHTML = `<div class="empty">No invoices yet.</div>`;
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
                <th>Due</th>
                <th class="num">Total</th>
                <th class="num">Paid</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              ${invoices
                .map((inv) => {
                  const canPay = !inv.is_voided && inv.paid_cents < inv.total_cents;
                  const canVoid = !inv.is_voided && inv.paid_cents === 0;
                  return `
                    <tr class="${inv.is_voided ? "voided" : ""}">
                      <td class="mono">${inv.id}</td>
                      <td>${esc(inv.customer_name)}</td>
                      <td class="mono">${esc(fmtDate(inv.date))}</td>
                      <td class="mono">${esc(fmtDate(inv.due_date))}</td>
                      <td class="num">${fmtMoney(inv.total_cents)}</td>
                      <td class="num">${fmtMoney(inv.paid_cents)}</td>
                      <td>${statusBadge(inv.status)}</td>
                      <td style="text-align:right;white-space:nowrap">
                        ${canPay ? `<button class="btn sm" data-pay="${inv.id}">Pay</button> ` : ""}
                        ${canVoid ? `<button class="btn sm danger" data-void="${inv.id}">Void</button>` : ""}
                      </td>
                    </tr>
                  `;
                })
                .join("")}
            </tbody>
          </table>
        </div>
      `;
      el.querySelectorAll("[data-pay]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const inv = invoices.find((i) => i.id === Number(btn.dataset.pay));
          if (inv) openPay(inv);
        });
      });
      el.querySelectorAll("[data-void]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const id = btn.dataset.void;
          if (!window.confirm(`Void invoice #${id}? This reverses its journal entry.`)) return;
          try {
            await API.voidInvoice(id);
            toast("Invoice voided", "success");
            await load();
          } catch (err) {
            toast(err.message, "error");
          }
        });
      });
    }

    container.querySelector("#f-customer").addEventListener("change", load);
    container.querySelector("#f-voided").addEventListener("change", load);
    container.querySelector("#refresh").addEventListener("click", load);

    await load();
  },
};
