// pages/periods.js — period locking: lock calendar months to protect their
// entries from changes (human or AI). Locking is idempotent; unlocking is the
// controlled reopen. The list doubles as lock history (a month's row is kept
// after an unlock), so the page shows every month that has ever been locked.
import { API } from "../api.js";
import { fmtDateTime, esc, toast, showFormError, clearFormError } from "../ui.js";
import { t } from "../i18n.js";

// Format a (year, month) pair as "YYYY-MM".
function ym(year, month) {
  return `${year}-${String(month).padStart(2, "0")}`;
}

export default {
  async render(container) {
    container.innerHTML = `
      <div class="page-head">
        <div>
          <h1 class="page-title">${t("nav.periods")}</h1>
          <p class="page-sub">${t("periods.subtitle")}</p>
        </div>
      </div>

      <div class="card">
        <h2>${t("periods.lock")}</h2>
        <form id="lock-form" class="stack" novalidate>
          <div class="form-row c2">
            <label class="field"><span>${t("periods.month")}</span>
              <input type="month" name="month" required /></label>
          </div>
          <div class="btn-row">
            <button type="submit" class="btn primary">${t("periods.lock_button")}</button>
          </div>
        </form>
      </div>

      <div class="card">
        <h2>${t("periods.history")}</h2>
        <div id="periods-list"><div class="empty">${t("common.loading")}</div></div>
      </div>
    `;

    const form = container.querySelector("#lock-form");
    const listEl = container.querySelector("#periods-list");

    async function loadList() {
      let periods;
      try {
        periods = await API.listPeriods();
      } catch (err) {
        toast(err.message, "error");
        return;
      }
      if (periods.length === 0) {
        listEl.innerHTML = `<div class="empty">${t("periods.no_match")}</div>`;
        return;
      }
      listEl.innerHTML = `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>${t("periods.month")}</th>
                <th>${t("common.status")}</th>
                <th>${t("periods.locked_at")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              ${periods
                .map((p) => {
                  const status = p.is_locked
                    ? `<span class="badge success">${t("periods.status_locked")}</span>`
                    : `<span class="badge">${t("periods.status_unlocked")}</span>`;
                  const btn = p.is_locked
                    ? `<button class="btn sm" data-unlock="${p.year}-${p.month}">${t("periods.unlock")}</button>`
                    : `<button class="btn sm" data-lock="${p.year}-${p.month}">${t("periods.relock")}</button>`;
                  return `
                    <tr>
                      <td class="mono">${ym(p.year, p.month)}</td>
                      <td>${status}</td>
                      <td class="mono">${esc(fmtDateTime(p.locked_at))}</td>
                      <td style="text-align:end;white-space:nowrap">${btn}</td>
                    </tr>
                  `;
                })
                .join("")}
            </tbody>
          </table>
        </div>
      `;
      listEl.querySelectorAll("[data-unlock]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const [year, month] = btn.dataset.unlock.split("-").map(Number);
          if (!window.confirm(t("periods.unlock_confirm", { month: ym(year, month) }))) return;
          try {
            await API.unlockPeriod(year, month);
            toast(t("periods.unlocked"), "success");
            await loadList();
          } catch (err) {
            toast(err.message, "error");
          }
        });
      });
      listEl.querySelectorAll("[data-lock]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const [year, month] = btn.dataset.lock.split("-").map(Number);
          try {
            await API.lockPeriod(year, month);
            toast(t("periods.locked"), "success");
            await loadList();
          } catch (err) {
            toast(err.message, "error");
          }
        });
      });
    }

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearFormError(form);
      const month = form.querySelector('[name="month"]').value;
      if (!month) {
        showFormError(form, t("periods.err_pick_month"));
        return;
      }
      const [year, m] = month.split("-").map(Number);
      try {
        await API.lockPeriod(year, m);
        toast(t("periods.locked"), "success");
        form.reset();
        await loadList();
      } catch (err) {
        showFormError(form, err.message);
      }
    });

    await loadList();
  },
};
