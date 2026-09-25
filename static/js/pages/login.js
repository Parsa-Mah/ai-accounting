// pages/login.js — first-run setup and login.
import { API } from "../api.js";
import { esc } from "../ui.js";

export default {
  async render(container) {
    const status = await API.authStatus();
    const isSetup = !status.configured;

    container.innerHTML = `
      <div class="auth-card">
        <h1>${isSetup ? "Set up your account" : "Sign in"}</h1>
        <p class="muted">
          ${isSetup
            ? "First run — create the single user account for this app."
            : "Enter your credentials to continue."}
        </p>
        <form id="auth-form" class="stack" novalidate>
          <label class="field">
            <span>Username</span>
            <input name="username" type="text" autocomplete="username" required />
          </label>
          <label class="field">
            <span>Password</span>
            <input
              name="password"
              type="password"
              autocomplete="${isSetup ? "new-password" : "current-password"}"
              minlength="6"
              required
            />
          </label>
          <button type="submit" class="btn primary">
            ${isSetup ? "Create account" : "Sign in"}
          </button>
          <div class="form-error" id="auth-error" hidden></div>
        </form>
      </div>
    `;

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
