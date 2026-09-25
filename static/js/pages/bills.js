// pages/bills.js — accounts payable: list, create (per-line expense account), pay, void.
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
    const [vendors, items, expenseAccounts] = await Promise.all([
      API.listVendors(),
      API.listItems(),
      API.listAccounts({ type: "expense" }),
    ]);
    const vendorOptions = vendors
      .map((v) => `<option value="${v.id}">${esc(v.name)}</option>`)
      .join("");

    container.innerHTML = `
      <div class="page-head">
        <div>
          <h1 class="page-title">Bills</h1>
          <p class="page-sub">Record what you owe (accounts payable).</p>
        </div>
        <div class="btn-row">
          <button id="toggle-new" class="btn primary" type="button">New bill</button>
        </div>
      </div>

      <div id="new-card" class="card" style="display:none">
        <h3>New bill</h3>
        ${expenseAccounts.length === 0 ? '<div class="form-error">No expense accounts available. Create one under Accounts first.</div>' : ""}
        <form id="new-form" class="stack" novalidate>
          <div class="form-row c3">
            <label class="field"><span>Vendor</span>
              <select name="vendor_id" required>${vendorOptions || '<option value="">No vendors yet</option>'}</select>
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
                    <th style="min-width:160px">Item</th>
                    <th>Description</th>
                    <th>Qty</th>
                    <th>Unit price</th>
                    <th style="min-width:200px">Expense account</th>
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
            <button type="submit" class="btn primary">Create bill</button>
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
        <label class="field"><span>Vendor</span>
          <select id="f-vendor"><option value="">all</option>${vendorOptions}</select>
        </label>
        <label class="field" style="flex-direction:row;align-items:center;gap:8px;padding-bottom:9px">
          <input type="checkbox" id="f-voided" style="width:auto" checked />
          <span style="font-weight:500">Include voided</span>
        </label>
        <button id="refresh" class="btn" type="button">Refresh</button>
      </div>

      <div id="bills-table"></div>
    `;

    const newCard = container.querySelector("#new-card");
    const toggleBtn = container.querySelector("#toggle-new");
    toggleBtn.addEventListener("click", () => {
      const hidden = newCard.style.display === "none";
      newCard.style.display = hidden ? "" : "none";
      toggleBtn.textContent = hidden ? "Hide form" : "New bill";
    });
    container.querySelector("#cancel-new").addEventListener("click", () => {
      newCard.style.display = "none";
      toggleBtn.textContent = "New bill";
    });

    const totalsEl = container.querySelector("#totals");
    const editor = createLineEditor({
      tbody: container.querySelector("#lines"),
      addBtn: container.querySelector("#add-line"),
      items,
      expenseAccounts,
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
        if (!l.expense_account_id) {
          showFormError(form, "Each line needs an expense account.");
          return;
        }
      }
      const body = {
        vendor_id: Number(fd.get("vendor_id")),
        date: fd.get("date"),
        due_date: fd.get("due_date") || null,
        tax_rate: Number(fd.get("tax_rate")) || 0,
        lines,
      };
      try {
        await API.createBill(body);
        toast("Bill created", "success");
        form.reset();
        form.querySelector('[name="date"]').value = todayISO();
        form.querySelector('[name="tax_rate"]').value = "0";
        container.querySelector("#lines").innerHTML = "";
        editor.addLine();
        newCard.style.display = "none";
        toggleBtn.textContent = "New bill";
        await load();
      } catch (err) {
        showFormError(form, err.message);
      }
    });

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
        await API.payBill(payTarget.id, {
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

    function openPay(bill) {
      payTarget = bill;
      const remaining = bill.total_cents - bill.paid_cents;
      payForm.querySelector('[name="amount"]').value = centsToDollars(remaining);
      payForm.querySelector('[name="date"]').value = todayISO();
      payForm.querySelector('[name="note"]').value = "";
      payCard.style.display = "";
      payCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    async function load() {
      const params = {};
      const vendor = container.querySelector("#f-vendor").value;
      params.include_voided = container.querySelector("#f-voided").checked;
      if (vendor) params.vendor_id = vendor;
      const bills = await API.listBills(params);
      renderTable(bills);
    }

    function renderTable(bills) {
      const el = container.querySelector("#bills-table");
      if (bills.length === 0) {
        el.innerHTML = `<div class="empty">No bills yet.</div>`;
        return;
      }
      el.innerHTML = `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Vendor</th>
                <th>Date</th>
                <th>Due</th>
                <th class="num">Total</th>
                <th class="num">Paid</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              ${bills
                .map((b) => {
                  const canPay = !b.is_voided && b.paid_cents < b.total_cents;
                  const canVoid = !b.is_voided && b.paid_cents === 0;
                  return `
                    <tr class="${b.is_voided ? "voided" : ""}">
                      <td class="mono">${b.id}</td>
                      <td>${esc(b.vendor_name)}</td>
                      <td class="mono">${esc(fmtDate(b.date))}</td>
                      <td class="mono">${esc(fmtDate(b.due_date))}</td>
                      <td class="num">${fmtMoney(b.total_cents)}</td>
                      <td class="num">${fmtMoney(b.paid_cents)}</td>
                      <td>${statusBadge(b.status)}</td>
                      <td style="text-align:right;white-space:nowrap">
                        ${canPay ? `<button class="btn sm" data-pay="${b.id}">Pay</button> ` : ""}
                        ${canVoid ? `<button class="btn sm danger" data-void="${b.id}">Void</button>` : ""}
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
          const bill = bills.find((x) => x.id === Number(btn.dataset.pay));
          if (bill) openPay(bill);
        });
      });
      el.querySelectorAll("[data-void]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const id = btn.dataset.void;
          if (!window.confirm(`Void bill #${id}? This reverses its journal entry.`)) return;
          try {
            await API.voidBill(id);
            toast("Bill voided", "success");
            await load();
          } catch (err) {
            toast(err.message, "error");
          }
        });
      });
    }

    container.querySelector("#f-vendor").addEventListener("change", load);
    container.querySelector("#f-voided").addEventListener("change", load);
    container.querySelector("#refresh").addEventListener("click", load);

    await load();
  },
};
