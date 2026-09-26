// pages/accounts.js — chart of accounts: list, filter, create, deactivate.
import { API } from "../api.js";
import { esc, statusBadge, toast, showFormError, clearFormError } from "../ui.js";
import { t } from "../i18n.js";

const TYPES = ["asset", "liability", "equity", "revenue", "expense"];

export default {
  async render(container) {
    const typeOptions = TYPES.map(
      (type) => `<option value="${type}">${t(`accounts.type_${type}`)}</option>`,
    ).join("");

    container.innerHTML = `
      <div class="page-head">
        <div>
          <h1 class="page-title">${t("nav.accounts")}</h1>
          <p class="page-sub">${t("accounts.subtitle")}</p>
        </div>
        <div class="btn-row">
          <button id="toggle-new" class="btn primary" type="button">${t("accounts.new")}</button>
        </div>
      </div>

      <div id="new-card" class="card" style="display:none">
        <h3>${t("accounts.new")}</h3>
        <form id="new-form" class="stack" novalidate>
          <div class="form-row c3">
            <label class="field"><span>${t("common.number")}</span>
              <input name="number" inputmode="numeric" placeholder="${t("accounts.ph_number")}" required />
            </label>
            <label class="field"><span>${t("common.name")}</span>
              <input name="name" placeholder="${t("accounts.ph_name")}" required />
            </label>
            <label class="field"><span>${t("common.type")}</span>
              <select name="type" required>${typeOptions}</select>
            </label>
          </div>
          <div class="form-row c3">
            <label class="field"><span>${t("accounts.subtype_optional")}</span>
              <input name="subtype" placeholder="${t("accounts.ph_subtype")}" />
            </label>
            <label class="field"><span>${t("accounts.bank_kind_optional")}</span>
              <input name="bank_kind" placeholder="${t("accounts.ph_bank_kind")}" />
            </label>
            <label class="field"><span>${t("accounts.description_optional")}</span>
              <input name="description" />
            </label>
          </div>
          <div class="btn-row">
            <button type="submit" class="btn primary">${t("common.create")}</button>
            <button type="button" id="cancel-new" class="btn ghost">${t("common.cancel")}</button>
          </div>
        </form>
      </div>

      <div class="toolbar">
        <label class="field"><span>${t("common.type")}</span>
          <select id="filter-type">
            <option value="">${t("common.all")}</option>
            ${typeOptions}
          </select>
        </label>
        <label class="field" style="flex-direction:row;align-items:center;gap:8px;padding-bottom:9px">
          <input type="checkbox" id="filter-inactive" style="width:auto" />
          <span style="font-weight:500">${t("accounts.include_inactive")}</span>
        </label>
        <button id="refresh" class="btn" type="button">${t("common.refresh")}</button>
      </div>

      <div id="accounts-table"></div>
    `;

    const newCard = container.querySelector("#new-card");
    const toggleBtn = container.querySelector("#toggle-new");
    toggleBtn.addEventListener("click", () => {
      const hidden = newCard.style.display === "none";
      newCard.style.display = hidden ? "" : "none";
      toggleBtn.textContent = hidden ? t("common.hide_form") : t("accounts.new");
    });
    container.querySelector("#cancel-new").addEventListener("click", () => {
      newCard.style.display = "none";
      toggleBtn.textContent = t("accounts.new");
    });

    const form = container.querySelector("#new-form");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearFormError(form);
      const fd = new FormData(form);
      const body = {
        number: fd.get("number").trim(),
        name: fd.get("name").trim(),
        type: fd.get("type"),
        subtype: fd.get("subtype").trim() || null,
        bank_kind: fd.get("bank_kind").trim() || null,
        description: fd.get("description").trim() || null,
      };
      try {
        await API.createAccount(body);
        toast(t("accounts.created"), "success");
        form.reset();
        newCard.style.display = "none";
        toggleBtn.textContent = t("accounts.new");
        await load();
      } catch (err) {
        showFormError(form, err.message);
      }
    });

    async function load() {
      const params = {};
      const type = container.querySelector("#filter-type").value;
      const inc = container.querySelector("#filter-inactive").checked;
      if (type) params.type = type;
      if (inc) params.include_inactive = true;
      const accounts = await API.listAccounts(params);
      renderTable(accounts);
    }

    function renderTable(accounts) {
      const el = container.querySelector("#accounts-table");
      if (accounts.length === 0) {
        el.innerHTML = `<div class="empty">${t("accounts.no_match")}</div>`;
        return;
      }
      el.innerHTML = `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>${t("common.number")}</th>
                <th>${t("common.name")}</th>
                <th>${t("common.type")}</th>
                <th>${t("accounts.subtype")}</th>
                <th>${t("common.bank")}</th>
                <th>${t("common.status")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              ${accounts
                .map((a) => {
                  const canDeactivate = a.is_active && !a.is_system;
                  return `
                    <tr class="${a.is_active ? "" : "voided"}">
                      <td class="mono">${esc(a.number)}</td>
                      <td>${esc(a.name)}${a.is_system ? ` <span class="badge">${t("accounts.system")}</span>` : ""}</td>
                      <td><span class="badge">${esc(a.type)}</span></td>
                      <td class="muted">${esc(a.subtype || "")}</td>
                      <td class="muted">${esc(a.bank_kind || "")}</td>
                      <td>${statusBadge(a.is_active ? "active" : "inactive")}</td>
                      <td style="text-align:right">
                        ${canDeactivate ? `<button class="btn sm danger" data-deactivate="${a.id}">${t("accounts.deactivate")}</button>` : ""}
                      </td>
                    </tr>
                  `;
                })
                .join("")}
            </tbody>
          </table>
        </div>
      `;
      el.querySelectorAll("[data-deactivate]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const id = btn.dataset.deactivate;
          if (!window.confirm(t("accounts.deactivate_confirm"))) return;
          try {
            await API.deactivateAccount(id);
            toast(t("accounts.deactivated"), "success");
            await load();
          } catch (err) {
            toast(err.message, "error");
          }
        });
      });
    }

    container.querySelector("#filter-type").addEventListener("change", load);
    container.querySelector("#filter-inactive").addEventListener("change", load);
    container.querySelector("#refresh").addEventListener("click", load);

    await load();
  },
};
