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
import { t } from "../i18n.js";

export default {
  async render(container) {
    const accounts = await API.listAccounts(); // active only
    const accountOptions = accounts
      .map((a) => `<option value="${a.id}">${esc(a.number)} — ${esc(a.name)}</option>`)
      .join("");

    container.innerHTML = `
      <div class="page-head">
        <div>
          <h1 class="page-title">${t("nav.journal")}</h1>
          <p class="page-sub">${t("journal.subtitle")}</p>
        </div>
        <div class="btn-row">
          <button id="toggle-new" class="btn primary" type="button">${t("journal.new")}</button>
        </div>
      </div>

      <div id="new-card" class="card" style="display:none">
        <h3>${t("journal.new_title")}</h3>
        <form id="new-form" class="stack" novalidate>
          <div class="form-row c2">
            <label class="field"><span>${t("common.date")}</span>
              <input type="date" name="date" value="${todayISO()}" required />
            </label>
            <label class="field"><span>${t("common.description")}</span>
              <input name="description" placeholder="${t("journal.ph_description")}" required />
            </label>
          </div>

          <div class="line-editor">
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th style="min-width:220px">${t("common.account")}</th>
                    <th>${t("common.description")}</th>
                    <th class="num" style="width:130px">${t("common.debit")}</th>
                    <th class="num" style="width:130px">${t("common.credit")}</th>
                    <th style="width:40px"></th>
                  </tr>
                </thead>
                <tbody id="lines"></tbody>
              </table>
            </div>
            <div class="btn-row" style="margin-top:10px">
              <button type="button" id="add-line" class="btn">${t("common.add_line")}</button>
              <span id="balance" class="muted"></span>
            </div>
          </div>

          <div class="btn-row">
            <button type="submit" class="btn primary">${t("journal.post")}</button>
            <button type="button" id="cancel-new" class="btn ghost">${t("common.cancel")}</button>
          </div>
        </form>
      </div>

      <div class="toolbar">
        <label class="field"><span>${t("common.from")}</span><input type="date" id="f-from" /></label>
        <label class="field"><span>${t("common.to")}</span><input type="date" id="f-to" /></label>
        <label class="field"><span>${t("common.account")}</span>
          <select id="f-account"><option value="">${t("common.all")}</option>${accountOptions}</select>
        </label>
        <label class="field" style="flex-direction:row;align-items:center;gap:8px;padding-bottom:9px">
          <input type="checkbox" id="f-voided" style="width:auto" checked />
          <span style="font-weight:500">${t("common.include_voided")}</span>
        </label>
        <button id="refresh" class="btn" type="button">${t("common.refresh")}</button>
      </div>

      <div id="journal-table"></div>
    `;

    // ----- New entry form -----
    const newCard = container.querySelector("#new-card");
    const toggleBtn = container.querySelector("#toggle-new");
    toggleBtn.addEventListener("click", () => {
      const hidden = newCard.style.display === "none";
      newCard.style.display = hidden ? "" : "none";
      toggleBtn.textContent = hidden ? t("common.hide_form") : t("journal.new");
    });
    container.querySelector("#cancel-new").addEventListener("click", () => {
      newCard.style.display = "none";
      toggleBtn.textContent = t("journal.new");
    });

    const tbody = container.querySelector("#lines");
    const balanceEl = container.querySelector("#balance");

    function addLine() {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><select class="line-account">${accountOptions}</select></td>
        <td><input class="line-desc" placeholder="${t("common.optional")}" /></td>
        <td><input class="line-debit num" inputmode="decimal" placeholder="0.00" /></td>
        <td><input class="line-credit num" inputmode="decimal" placeholder="0.00" /></td>
        <td style="text-align:center"><button type="button" class="line-remove" title="${t("common.remove_line")}">&times;</button></td>
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
          ? `<span class="muted">${t("journal.balanced")}</span>`
          : `<span style="color:var(--danger)">${t("journal.off_by", { amount: fmtMoney(diff) })}</span>`;
      balanceEl.innerHTML = t("journal.totals", {
        debits: fmtMoney(d),
        credits: fmtMoney(c),
        state,
      });
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
          showFormError(form, t("journal.err_invalid_amount"));
          return;
        }
        if (debit > 0 && credit > 0) {
          showFormError(form, t("journal.err_both_sides"));
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
        showFormError(form, t("journal.err_no_lines"));
        return;
      }
      const totalDebit = lines.reduce((s, l) => s + l.debit, 0);
      const totalCredit = lines.reduce((s, l) => s + l.credit, 0);
      if (totalDebit !== totalCredit) {
        showFormError(
          form,
          t("journal.err_unbalanced", { debits: fmtMoney(totalDebit), credits: fmtMoney(totalCredit) }),
        );
        return;
      }

      try {
        await API.createJournal({ date, description, lines });
        toast(t("journal.posted"), "success");
        form.reset();
        form.querySelector('[name="date"]').value = todayISO();
        tbody.innerHTML = "";
        addLine();
        newCard.style.display = "none";
        toggleBtn.textContent = t("journal.new");
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
        el.innerHTML = `<div class="empty">${t("journal.no_match")}</div>`;
        return;
      }
      el.innerHTML = `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>${t("common.id")}</th>
                <th>${t("common.date")}</th>
                <th>${t("common.description")}</th>
                <th>${t("common.source")}</th>
                <th class="num">${t("common.amount")}</th>
                <th>${t("common.status")}</th>
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
                        ${canVoid ? `<button class="btn sm danger" data-void="${e.id}">${t("common.void")}</button>` : ""}
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
          if (!window.confirm(t("journal.void_confirm", { id }))) return;
          try {
            await API.voidJournal(id);
            toast(t("journal.voided"), "success");
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
