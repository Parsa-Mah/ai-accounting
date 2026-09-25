// pages/accounts.js — chart of accounts: list, filter, create, deactivate.
import { API } from "../api.js";
import { esc, statusBadge, toast, showFormError, clearFormError } from "../ui.js";

const TYPES = ["asset", "liability", "equity", "revenue", "expense"];

export default {
  async render(container) {
    container.innerHTML = `
      <div class="page-head">
        <div>
          <h1 class="page-title">Accounts</h1>
          <p class="page-sub">Your chart of accounts.</p>
        </div>
        <div class="btn-row">
          <button id="toggle-new" class="btn primary" type="button">New account</button>
        </div>
      </div>

      <div id="new-card" class="card" style="display:none">
        <h3>New account</h3>
        <form id="new-form" class="stack" novalidate>
          <div class="form-row c3">
            <label class="field"><span>Number</span>
              <input name="number" inputmode="numeric" placeholder="e.g. 1200" required />
            </label>
            <label class="field"><span>Name</span>
              <input name="name" placeholder="e.g. Utilities" required />
            </label>
            <label class="field"><span>Type</span>
              <select name="type" required>
                ${TYPES.map((t) => `<option value="${t}">${t}</option>`).join("")}
              </select>
            </label>
          </div>
          <div class="form-row c3">
            <label class="field"><span>Subtype (optional)</span>
              <input name="subtype" placeholder="e.g. cogs" />
            </label>
            <label class="field"><span>Bank kind (optional)</span>
              <input name="bank_kind" placeholder="checking / savings" />
            </label>
            <label class="field"><span>Description (optional)</span>
              <input name="description" />
            </label>
          </div>
          <div class="btn-row">
            <button type="submit" class="btn primary">Create</button>
            <button type="button" id="cancel-new" class="btn ghost">Cancel</button>
          </div>
        </form>
      </div>

      <div class="toolbar">
        <label class="field"><span>Type</span>
          <select id="filter-type">
            <option value="">all</option>
            ${TYPES.map((t) => `<option value="${t}">${t}</option>`).join("")}
          </select>
        </label>
        <label class="field" style="flex-direction:row;align-items:center;gap:8px;padding-bottom:9px">
          <input type="checkbox" id="filter-inactive" style="width:auto" />
          <span style="font-weight:500">Include inactive</span>
        </label>
        <button id="refresh" class="btn" type="button">Refresh</button>
      </div>

      <div id="accounts-table"></div>
    `;

    const newCard = container.querySelector("#new-card");
    const toggleBtn = container.querySelector("#toggle-new");
    toggleBtn.addEventListener("click", () => {
      const hidden = newCard.style.display === "none";
      newCard.style.display = hidden ? "" : "none";
      toggleBtn.textContent = hidden ? "Hide form" : "New account";
    });
    container.querySelector("#cancel-new").addEventListener("click", () => {
      newCard.style.display = "none";
      toggleBtn.textContent = "New account";
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
        toast("Account created", "success");
        form.reset();
        newCard.style.display = "none";
        toggleBtn.textContent = "New account";
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
        el.innerHTML = `<div class="empty">No accounts match.</div>`;
        return;
      }
      el.innerHTML = `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Number</th>
                <th>Name</th>
                <th>Type</th>
                <th>Subtype</th>
                <th>Bank</th>
                <th>Status</th>
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
                      <td>${esc(a.name)}${a.is_system ? ' <span class="badge">system</span>' : ""}</td>
                      <td><span class="badge">${esc(a.type)}</span></td>
                      <td class="muted">${esc(a.subtype || "")}</td>
                      <td class="muted">${esc(a.bank_kind || "")}</td>
                      <td>${statusBadge(a.is_active ? "active" : "inactive")}</td>
                      <td style="text-align:right">
                        ${canDeactivate ? `<button class="btn sm danger" data-deactivate="${a.id}">Deactivate</button>` : ""}
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
          if (!window.confirm("Deactivate this account? It will no longer be usable in new entries.")) return;
          try {
            await API.deactivateAccount(id);
            toast("Account deactivated", "success");
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
