// doclines.js — reusable line editor for document lines (invoices/estimates/bills).
//
// Each line: optional item (auto-fills description + price), description,
// quantity, unit price (typed in dollars). Bills add a required expense account.
// Money is kept as integer cents internally; the UI shows dollars.
import { esc, dollarsToCents, fmtMoney } from "./ui.js";

export function createLineEditor({
  tbody,
  addBtn,
  items = [],
  expenseAccounts = null,
  onTotal = null,
}) {
  function itemOptions() {
    const custom = `<option value="">— custom line —</option>`;
    const opts = items
      .map(
        (i) =>
          `<option value="${i.id}" data-price="${i.unit_price_cents}" data-name="${esc(i.name)}">${esc(i.name)}</option>`,
      )
      .join("");
    return custom + opts;
  }

  function expenseOptions() {
    return expenseAccounts
      .map(
        (a) =>
          `<option value="${a.id}">${esc(a.number)} — ${esc(a.name)}</option>`,
      )
      .join("");
  }

  function addLine() {
    const expenseCell = expenseAccounts
      ? `<td><select class="line-expense">${expenseOptions()}</select></td>`
      : "";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><select class="line-item">${itemOptions()}</select></td>
      <td><input class="line-desc" placeholder="Description" /></td>
      <td style="width:70px"><input class="line-qty" type="number" min="1" value="1" /></td>
      <td style="width:110px"><input class="line-price" inputmode="decimal" placeholder="0.00" /></td>
      ${expenseCell}
      <td class="num line-amount"></td>
      <td style="width:40px;text-align:center"><button type="button" class="line-remove" title="Remove line">&times;</button></td>
    `;
    tbody.appendChild(tr);

    const itemSel = tr.querySelector(".line-item");
    itemSel.addEventListener("change", () => {
      const opt = itemSel.selectedOptions[0];
      if (opt && opt.value) {
        tr.querySelector(".line-desc").value = opt.dataset.name;
        tr.querySelector(".line-price").value = (Number(opt.dataset.price) / 100).toFixed(2);
      }
      update();
    });
    tr.querySelector(".line-remove").addEventListener("click", () => {
      tr.remove();
      update();
    });
    tr.querySelectorAll(".line-qty, .line-price").forEach((inp) =>
      inp.addEventListener("input", update),
    );
    update();
  }

  // Read all lines into API-ready objects (money in cents).
  function lines() {
    const out = [];
    for (const tr of tbody.querySelectorAll("tr")) {
      const itemId = tr.querySelector(".line-item").value;
      const line = {
        item_id: itemId ? Number(itemId) : null,
        description: tr.querySelector(".line-desc").value.trim() || null,
        quantity: Number(tr.querySelector(".line-qty").value) || 1,
        unit_price_cents: dollarsToCents(tr.querySelector(".line-price").value),
      };
      if (expenseAccounts) {
        line.expense_account_id = Number(tr.querySelector(".line-expense").value);
      }
      out.push(line);
    }
    return out;
  }

  // Sum line amounts (qty * unit price) and update each row's amount cell.
  function totals() {
    let subtotal = 0;
    for (const tr of tbody.querySelectorAll("tr")) {
      const qty = Number(tr.querySelector(".line-qty").value) || 0;
      const price = dollarsToCents(tr.querySelector(".line-price").value) || 0;
      const amt = qty * price;
      tr.querySelector(".line-amount").textContent = amt ? fmtMoney(amt) : "";
      subtotal += amt;
    }
    return subtotal;
  }

  function update() {
    const subtotal = totals();
    if (onTotal) onTotal(subtotal);
  }

  addBtn.addEventListener("click", addLine);
  addLine();
  return { addLine, lines, totals, update };
}
