// router.js — hash-based router and SPA entry point.
//
// Each route lazily imports its page module (code splitting). A page module
// default-exports { render(container) }. Routes that have no page module yet
// render a "still being built" placeholder, so the shell works incrementally.
import { API } from "./api.js";

const NAV = [
  ["dashboard", "Dashboard"],
  ["accounts", "Accounts"],
  ["journal", "Journal"],
  ["ledger", "Ledger"],
  ["statements", "Statements"],
  ["invoices", "Invoices"],
  ["estimates", "Estimates"],
  ["bills", "Bills"],
  ["budgets", "Budgets"],
  ["reconciliation", "Reconciliation"],
  ["export", "Export"],
];

const LOADERS = {
  login: () => import("./pages/login.js"),
  dashboard: () => import("./pages/dashboard.js"),
  accounts: () => import("./pages/accounts.js"),
  journal: () => import("./pages/journal.js"),
  ledger: () => import("./pages/ledger.js"),
  statements: () => import("./pages/statements.js"),
  invoices: () => import("./pages/invoices.js"),
  estimates: () => import("./pages/estimates.js"),
  bills: () => import("./pages/bills.js"),
  budgets: () => import("./pages/budgets.js"),
  reconciliation: () => import("./pages/reconciliation.js"),
  export: () => import("./pages/export.js"),
};

let currentUser = null;

function currentRoute() {
  const hash = window.location.hash.replace(/^#\/?/, "");
  return hash || "dashboard";
}

async function ensureAuth() {
  if (currentUser) return true;
  try {
    currentUser = await API.me();
    return true;
  } catch {
    currentUser = null;
    return false;
  }
}

function renderNav(active) {
  const nav = document.getElementById("nav");
  nav.innerHTML = "";
  for (const [key, label] of NAV) {
    const a = document.createElement("a");
    a.href = `#/${key}`;
    a.className = "nav-link" + (key === active ? " active" : "");
    a.textContent = label;
    nav.appendChild(a);
  }
}

function placeholder(container, name) {
  container.innerHTML = `
    <div class="card">
      <h2>${name}</h2>
      <div class="empty">This page is still being built.</div>
    </div>
  `;
}

async function render() {
  const route = currentRoute();
  const app = document.getElementById("app");
  const topbar = document.getElementById("topbar");

  // Auth gate: everything except login requires a valid session.
  if (route !== "login") {
    const ok = await ensureAuth();
    if (!ok) {
      window.location.hash = "#/login";
      return;
    }
  }

  if (route === "login") {
    document.body.classList.add("auth-mode");
    topbar.style.display = "none";
  } else {
    document.body.classList.remove("auth-mode");
    topbar.style.display = "";
    renderNav(route);
    const userEl = document.getElementById("username");
    if (userEl && currentUser) userEl.textContent = currentUser.username;
  }

  app.innerHTML = "";
  const loader = LOADERS[route] || LOADERS.dashboard;
  try {
    const mod = await loader();
    await mod.default.render(app);
  } catch {
    const name = route.charAt(0).toUpperCase() + route.slice(1);
    placeholder(app, name);
  }
}

window.addEventListener("hashchange", render);

async function init() {
  const logoutBtn = document.getElementById("logout");
  logoutBtn.addEventListener("click", async () => {
    try {
      await API.logout();
    } catch {
      // ignore — we redirect regardless
    }
    currentUser = null;
    window.location.hash = "#/login";
  });

  if (!window.location.hash || window.location.hash === "#/") {
    window.location.hash = "#/dashboard";
  }
  await render();
}

document.addEventListener("DOMContentLoaded", init);
