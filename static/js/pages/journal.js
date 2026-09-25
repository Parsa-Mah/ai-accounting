// pages/journal.js — the double-entry core: list, create (line editor), void.
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
  dollarsToCents,
} from "../ui.js";

export default {
  async render(container) {
    const accounts = await API.listAccounts(); // active only
    const accountOptions = accounts
      .map((a) => `<option value="${a.id}">${esc(a.number)} — ${esc(a.name)}</option>`)
      .join("");

    container.innerHTML = `
      <div class="page-head">
        <div>
          <h1 class="page-title">Journal</h1>
          <p class="page-sub">Every financial event posts through here.</p>
        </div>
        <div class="btn-row">
          <button id="toggle-new" class="btn primary" type="button">New entry</button>
        </div>
      </div>

      <div id="new-card" class="card" style="display:none">
        <h3>New journal entry</h3>
        <form id="new-form" class="stack" novalidate>
          <div class="form-row c2">
            <label class="field"><span>Date</span>
              <input type="date" name="date" value="${todayISO()}" required />
            </label>
            <label class="field"><span>Description</span>
              <input name="description" placeholder="e.g. Owner investment" required />
            </label>
          </div>

          <div class="line-editor">
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th style="min-width:220px">Account</th>
                    <th>Description</th>
                    <th class="num" style="width:130px">Debit</th>
                    <th class="num" style="width:130px">Credit</th>
                    <th style="width:40px"></th>
                  </tr>
                </thead>
                <tbody id="lines"></tbody>
              </table>
            </div>
            <div class="btn-row" style="margin-top:10px">
              <button type="button" id="add-line" class="btn">Add line</button>
              <span id="balance" class="muted"></span>
            </div>
          </div>

          <div class="btn-row">
            <button type="submit" class="btn primary">Post entry</button>
            <button type="button" id="cancel-new" class="btn ghost">Cancel</button>
          </div>
        </form>
      </div>

      <div class="toolbar">
        <label class="field"><span>From</span><input type="date" id="f-from" /></label>
        <label class="field"><span>To</span><input type="date" id="f-to" /></label>
        <label class="field"><span>Account</span>
          <select id="f-account"><option value="">all</option>${accountOptions}</select>
        </label>
        <label class="field" style="flex-direction:row;align-items:center;gap:8px;padding-bottom:9px">
          <input type="checkbox" id="f-voided" style="width:auto" checked />
          <span style="font-weight:500">Include voided</span>
        </label>
        <button id="refresh" class="btn" type="button">Refresh</button>
      </div>

      <div id="journal-table"></div>
    `;

    // ----- New entry form -----
    const newCard = container.querySelector("#new-card");
    const toggleBtn = container.querySelector("#toggle-new");
    toggleBtn.addEventListener("click", () => {
      const hidden = newCard.style.display === "none";
      newCard.style.display = hidden ? "" : "none";
      toggleBtn.textContent = hidden ? "Hide form" : "New entry";
    });
    container.querySelector("#cancel-new").addEventListener("click", () => {
      newCard.style.display = "none";
      toggleBtn.textContent = "New entry";
    });

    const tbody = container.querySelector("#lines");
    const balanceEl = container.querySelector("#balance");

    function addLine() {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><select class="line-account">${accountOptions}</select></td>
        <td><input class="line-desc" placeholder="optional" /></td>
        <td><input class="line-debit num" inputmode="decimal" placeholder="0.00" /></td>
        <td><input class="line-credit num" inputmode="decimal" placeholder="0.00" /></td>
        <td style="text-align:center"><button type="button" class="line-remove" title="Remove line">&times;</button></td>
      `;
      tbody.appendChild(tr);
      tr.querySelector(".line-remove").addEventListener("click", () => {
        tr.remove();
        updateTotals();
      });
      tr.querySelectorAll(".line-debit, .line-credit").forEach((inp) =>
        inp.addEventListener("input", updateTotals),
      );
      updateTotals();
    }

    function updateTotals() {
      let d = 0;
      let c = 0;
      tbody.querySelectorAll("tr").forEach((tr) => {
        d += dollarsToCents(tr.querySelector(".line-debit").value) || 0;
        c += dollarsToCents(tr.querySelector(".line-credit").value) || 0;
      });
      const diff = d - c;
      const state =
        diff === 0
          ? `<span class="muted">Balanced</span>`
          : `<span style="color:var(--danger)">Off by ${fmtMoney(diff)}</span>`;
      balanceEl.innerHTML = `Debits <b>${fmtMoney(d)}</b> &middot; Credits <b>${fmtMoney(c)}</b> &middot; ${state}`;
    }

    container.querySelector("#add-line").addEventListener("click", addLine);
    addLine(); // start with one line

    const form = container.querySelector("#new-form");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearFormError(form);
      const fd = new FormData(form);
      const date = fd.get("date");
      const description = fd.get("description").trim();

      const lines = [];
      for (const tr of tbody.querySelectorAll("tr")) {
        const accountId = Number(tr.querySelector(".line-account").value);
        const desc = tr.querySelector(".line-desc").value.trim();
        const debit = dollarsToCents(tr.querySelector(".line-debit").value);
        const credit = dollarsToCents(tr.querySelector(".line-credit").value);
        if (Number.isNaN(debit) || Number.isNaN(credit)) {
          showFormError(form, "A line has an invalid amount.");
          return;
        }
        if (debit > 0 && credit > 0) {
          showFormError(form, "A line has both a debit and a credit. Each line is one or the other.");
          return;
        }
        if (debit === 0 && credit === 0) continue; // skip empty lines
        lines.push({
          account_id: accountId,
          description: desc || null,
          debit,
          credit,
        });
      }
      if (lines.length === 0) {
        showFormError(form, "Add at least one line with a debit or credit.");
        return;
      }
      const totalDebit = lines.reduce((s, l) => s + l.debit, 0);
      const totalCredit = lines.reduce((s, l) => s + l.credit, 0);
      if (totalDebit !== totalCredit) {
        showFormError(form, `Entry does not balance: debits ${fmtMoney(totalDebit)} vs credits ${fmtMoney(totalCredit)}.`);
        return;
      }

      try {
        await API.createJournal({ date, description, lines });
        toast("Entry posted", "success");
        form.reset();
        form.querySelector('[name="date"]').value = todayISO();
        tbody.innerHTML = "";
        addLine();
        newCard.style.display = "none";
        toggleBtn.textContent = "New entry";
        await load();
      } catch (err) {
        showFormError(form, err.message);
      }
    });

    // ----- List -----
    async function load() {
      const params = {};
      const from = container.querySelector("#f-from").value;
      const to = container.querySelector("#f-to").value;
      const account = container.querySelector("#f-account").value;
      const incVoided = container.querySelector("#f-voided").checked;
      if (from) params.date_from = from;
      if (to) params.date_to = to;
      if (account) params.account_id = account;
      params.include_voided = incVoided;
      const entries = await API.listJournal(params);
      renderTable(entries);
    }

    function renderTable(entries) {
      const el = container.querySelector("#journal-table");
      if (entries.length === 0) {
        el.innerHTML = `<div class="empty">No journal entries match.</div>`;
        return;
      }
      el.innerHTML = `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Date</th>
                <th>Description</th>
                <th>Source</th>
                <th class="num">Amount</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              ${entries
                .map((e) => {
                  const total = e.lines.reduce((s, l) => s + l.debit, 0);
                  const canVoid = !e.is_voided && e.source_type !== "void";
                  return `
                    <tr class="${e.is_voided ? "voided" : ""}">
                      <td class="mono">${e.id}</td>
                      <td class="mono">${esc(fmtDate(e.date))}</td>
                      <td>${esc(e.description)}</td>
                      <td><span class="badge">${esc(e.source_type)}</span></td>
                      <td class="num">${fmtMoney(total)}</td>
                      <td>${e.is_voided ? statusBadge("void") : statusBadge("active")}</td>
                      <td style="text-align:right">
                        ${canVoid ? `<button class="btn sm danger" data-void="${e.id}">Void</button>` : ""}
                      </td>
                    </tr>
                  `;
                })
                .join("")}
            </tbody>
          </table>
        </div>
      `;
      el.querySelectorAll("[data-void]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const id = btn.dataset.void;
          if (!window.confirm(`Void entry #${id}? This posts a reversing entry (history is kept).`)) return;
          try {
            await API.voidJournal(id);
            toast("Entry voided", "success");
            await load();
          } catch (err) {
            toast(err.message, "error");
          }
        });
      });
    }

    container.querySelector("#f-from").addEventListener("change", load);
    container.querySelector("#f-to").addEventListener("change", load);
    container.querySelector("#f-account").addEventListener("change", load);
    container.querySelector("#f-voided").addEventListener("change", load);
    container.querySelector("#refresh").addEventListener("click", load);

    await load();
  },
};
