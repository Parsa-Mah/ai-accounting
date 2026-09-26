// i18n.js — internationalization for the SPA.
//
// One JSON dictionary per language at /i18n/{code}.json. The browser consumes
// the "ui" section: flat "namespace.key" -> string. t(key, vars) substitutes
// {var} placeholders; missing keys fall back to English, then to the key.
//
// Language choice: localStorage("lang") -> browser language -> "en".
// setLang() persists the choice, updates <html lang/dir>, and asks the router
// to re-render via the "i18n:changed" document event.
//
// Adding a language: create static/i18n/{code}.json with the same "ui" keys
// as en.json and append { code, name, dir? } to LANGS below. tests/test_i18n.py
// enforces key and placeholder parity across all dictionaries.

// Available languages, in UI order. `dir` is set for RTL languages.
export const LANGS = [{ code: "en", name: "English" }];

let current = "en";
const cache = {};

export function lang() {
  return current;
}

export function detectLang() {
  const saved = localStorage.getItem("lang");
  if (saved && LANGS.some((l) => l.code === saved)) return saved;
  const navLangs = navigator.languages || [navigator.language];
  for (const nav of navLangs) {
    const code = String(nav || "").toLowerCase();
    if (!code) continue;
    if (LANGS.some((l) => l.code === code)) return code;
    const prefix = code.split("-")[0];
    if (LANGS.some((l) => l.code === prefix)) return prefix;
  }
  return "en";
}

async function loadDict(code) {
  if (cache[code]) return cache[code];
  const res = await fetch(`/i18n/${code}.json`);
  if (!res.ok) throw new Error(`Could not load language ${code}`);
  cache[code] = await res.json();
  return cache[code];
}

let ready = null;

// Load the active language's dictionary. Await this before the first render.
export function initI18n() {
  if (!ready) {
    current = detectLang();
    ready = loadDict(current).catch(() => loadDict("en"));
  }
  return ready;
}

export async function setLang(code) {
  if (!LANGS.some((l) => l.code === code) || code === current) return;
  const prev = current;
  current = code;
  try {
    await loadDict(code);
  } catch {
    current = prev;
    return;
  }
  localStorage.setItem("lang", code);
  applyHtmlAttrs();
  document.dispatchEvent(new CustomEvent("i18n:changed", { detail: { lang: current } }));
}

function applyHtmlAttrs() {
  const entry = LANGS.find((l) => l.code === current);
  document.documentElement.lang = current;
  if (entry && entry.dir) document.documentElement.dir = entry.dir;
  else document.documentElement.removeAttribute("dir");
}

// Translate a ui-section string. vars substitutes {name} placeholders.
// Values may contain HTML; escape user data before interpolating.
export function t(key, vars) {
  let s = lookup("ui", key);
  if (s === undefined) s = key;
  if (vars) {
    for (const [name, value] of Object.entries(vars)) {
      s = s.split(`{${name}}`).join(String(value));
    }
  }
  return s;
}

function lookup(section, key) {
  const dict = cache[current];
  let value = dict && dict[section] ? dict[section][key] : undefined;
  if (value === undefined && current !== "en") {
    const en = cache["en"];
    value = en && en[section] ? en[section][key] : undefined;
  }
  return value;
}

// <option> markup for a language <select>.
export function langOptions(selected) {
  return LANGS.map(
    (l) =>
      `<option value="${l.code}"${l.code === selected ? " selected" : ""}>${l.name}</option>`,
  ).join("");
}

// Wire a <select> (class "lang-select") to language changes.
export function wireLangSelect(select) {
  select.addEventListener("change", () => setLang(select.value));
}
