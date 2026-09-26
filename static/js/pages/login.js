// pages/login.js — first-run setup and login.
import { API } from "../api.js";
import { esc } from "../ui.js";
import { lang, t, langOptions, wireLangSelect } from "../i18n.js";

export default {
  async render(container) {
    const status = await API.authStatus();
    const isSetup = !status.configured;

    container.innerHTML = `
      <div class="auth-card">
        <h1>${t(isSetup ? "auth.setup_title" : "auth.login_title")}</h1>
        <p class="muted">
          ${t(isSetup ? "auth.setup_subtitle" : "auth.login_subtitle")}
        </p>
        <form id="auth-form" class="stack" novalidate>
          <label class="field">
            <span>${t("common.username")}</span>
            <input name="username" type="text" autocomplete="username" required />
          </label>
          <label class="field">
            <span>${t("common.password")}</span>
            <input
              name="password"
              type="password"
              autocomplete="${isSetup ? "new-password" : "current-password"}"
              minlength="6"
              required
            />
          </label>
          <button type="submit" class="btn primary">
            ${t(isSetup ? "auth.setup_button" : "auth.login_button")}
          </button>
          <div class="form-error" id="auth-error" hidden></div>
        </form>
        <select id="lang-login" class="lang-select" aria-label="Language">${langOptions(lang())}</select>
      </div>
    `;

    wireLangSelect(container.querySelector("#lang-login"));

    const form = container.querySelector("#auth-form");
    const errEl = container.querySelector("#auth-error");

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      errEl.hidden = true;
      const fd = new FormData(form);
      const username = fd.get("username");
      const password = fd.get("password");
      try {
        if (isSetup) {
          await API.setup(username, password);
        } else {
          await API.login(username, password);
        }
        window.location.hash = "#/dashboard";
      } catch (err) {
        errEl.textContent = err.message;
        errEl.hidden = false;
      }
    });
  },
};
