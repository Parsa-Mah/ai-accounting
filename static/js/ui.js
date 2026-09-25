// ui.js — shared UI helpers: formatting, escaping, toasts, small builders.

// Format integer cents as USD. Negative values render with a leading minus.
export function fmtMoney(cents) {
  if (cents === null || cents === undefined) return "";
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(Number(cents));
  const dollars = Math.floor(abs / 100);
  const rem = Math.abs(Math.round(abs) % 100);
  return `${sign}$${dollars.toLocaleString("en-US")}.${String(rem).padStart(2, "0")}`;
}

// Parse a user-typed dollar amount ("1,234.56", "$10") into integer cents.
// Returns NaN for non-numeric input, 0 for empty.
export function dollarsToCents(str) {
  const s = String(str).trim().replace(/[$,\s]/g, "");
  if (s === "") return 0;
  const n = Number(s);
  if (Number.isNaN(n)) return NaN;
  return Math.round(n * 100);
}

// Format integer cents as a plain dollar string for use in number inputs.
export function centsToDollars(cents) {
  return (Number(cents) / 100).toFixed(2);
}

// Render a date value (ISO string "YYYY-MM-DD" or Date) as "YYYY-MM-DD".
export function fmtDate(d) {
  if (!d) return "";
  if (d instanceof Date) return d.toISOString().slice(0, 10);
  return String(d).slice(0, 10);
}

// Today's date as an ISO string (local time).
export function todayISO() {
  const d = new Date();
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10);
}

// HTML-escape a value for safe interpolation into innerHTML.
export function esc(s) {
  if (s === null || s === undefined) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Build a status badge. Maps known statuses to a tone.
const STATUS_TONE = {
  open: "info",
  partially_paid: "warning",
  paid: "success",
  void: "danger",
  voided: "danger",
  converted: "success",
  active: "success",
  inactive: "danger",
};

export function statusBadge(status) {
  const tone = STATUS_TONE[status] || "";
  const label = String(status || "").replace(/_/g, " ");
  return `<span class="badge ${tone}">${esc(label)}</span>`;
}

let toastTimer = null;
// Show a transient toast message. type: info | success | error
export function toast(message, type = "info") {
  let t = document.getElementById("toast");
  if (!t) {
    t = document.createElement("div");
    t.id = "toast";
    t.className = "toast";
    document.body.appendChild(t);
  }
  t.textContent = message;
  t.className = `toast show ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    t.className = `toast ${type}`;
  }, 3200);
}

// Read a form's text/number/select fields into a plain object by name.
export function readForm(form) {
  const out = {};
  for (const el of form.querySelectorAll("[name]")) {
    if (el.type === "checkbox") {
      out[el.name] = el.checked;
    } else {
      out[el.name] = el.value;
    }
  }
  return out;
}

// Show an inline error inside a container (creates a .form-error if needed).
export function showFormError(container, message) {
  let el = container.querySelector(":scope > .form-error");
  if (!el) {
    el = document.createElement("div");
    el.className = "form-error";
    container.appendChild(el);
  }
  el.textContent = message;
  el.hidden = false;
}

export function clearFormError(container) {
  const el = container.querySelector(":scope > .form-error");
  if (el) el.hidden = true;
}

// Convenience: build an element with attributes and children.
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") {
      node.addEventListener(k.slice(2), v);
    } else if (v !== null && v !== undefined && v !== false) {
      node.setAttribute(k, v === true ? "" : v);
    }
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined) continue;
    node.append(child.nodeType ? child : document.createTextNode(child));
  }
  return node;
}
