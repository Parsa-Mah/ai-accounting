# AIHelper — Accounting

## Project Summary

Python accounting web application (double-entry bookkeeping core + invoicing, AR/AP, budgets, CSV/PDF export). The project exists to demonstrate that a **local AI model writes the entire application** — the app is the vehicle, AI authorship is the product.

## Project Goals

1. Primary: a complete, working accounting app authored 100% by AI (no human-written code).
2. Secondary: a real, coherent accounting domain implementation (not a toy).
3. Public presentation: README + `AI_WORKFLOW.md` must make AI authorship explicit (model, runtime, hardware).

## Current Project Status

**Build complete.** All 13 phases (0–12) are implemented and tested: 208/208 tests passing (incl. 6 i18n + 4 README i18n parity tests), pyright 0 errors. Git: branch `main`, tracking `origin/main` (GitHub: `Parsa-Mah/ai-accounting`). Any new work is post-build (features, fixes, polish).

**Post-build — i18n (UI localization) in progress.** Phase 0 is complete: i18n infrastructure (`js/i18n.js`), the English baseline dictionary (`static/i18n/en.json`), all 16 frontend JS files refactored to `t()`, a language selector (topbar + login), and `tests/test_i18n.py`. Batch 1 is complete: 5 languages added (`fr, de, it, es, pt`); Batch 2 is complete: 5 more added (`sq, be, bg, ca, hr`); Batch 3 is complete: 3 more added (`cs, da, et`); Batch 4 is complete: 3 more added (`fi, el, hu`); Batch 5 is complete: 3 more added (`is, ga, lv`); Batch 6 is complete: 3 more added (`lt, lb, mk`); Batch 7 is complete: 3 more added (`no, pl, ro`); Batch 8 is complete: 3 more added (`ru, sr, sl`); Batch 9 is complete: 3 more added (`sk, sv, uk`); Batch 10 is complete: 3 more added (`ar, hy, az`); Batch 11 is complete: 3 more added (`prs, ka, he`) — all wired into `LANGS`. The localization target is now **84 languages** (39 done, 45 queued — see "i18n — language queue" below), to be added in batches of ~3. **Each language batch adds only the app translation (i18n dictionary + `LANGS` entry); README translations are done in their own separate batches, not bundled with the language batches** (see below). Persian `fa` is the first RTL language (it introduced the RTL layout); Arabic `ar`, Dari `prs`, and Hebrew `he` follow. The README's "Languages supported" section lists the per-country coverage.

**Post-build — README translations in progress.** The README is translated per language to a root `README.{code}.md` (English baseline `README.md`) with a generated language-switcher block linking them. Two of 84 are done (`en`, `fa`); 82 queued. **README translations are deliberately decoupled from the app-dictionary language batches** — a language batch touches only `static/i18n/{code}.json` + `LANGS`; the READMEs are translated later, in their own batches, following the same queue order (RTL last). See "README translations" below.

## Architecture

Stack: Python 3.12 · FastAPI + uvicorn · SQLAlchemy 2.0 · SQLite (`accounting.db`) · vanilla HTML/CSS/JS SPA frontend (no build step) · ReportLab (PDF export) · MCP Python SDK v2 (`mcp>=2`) · pytest + TestClient.

```
Accounting/
├── main.py            # entry point: uvicorn runner (+ --seed flag)
├── mcp_server.py      # MCP entry point: stdio (default) + streamable-HTTP, --print-config
├── app/
│   ├── main.py        # FastAPI app factory, mounts, DB init, exception handlers
│   ├── database.py    # engine, session, schema init, COA seed hook
│   ├── dependencies.py# get_current_user (cookie session auth)
│   ├── models/        # Account, AccountType, User, JournalEntry, JournalLine, Customer, Vendor, Item, Invoice, Estimate, Bill, Budget, Reconciliation
│   ├── schemas/       # Pydantic v2 request/response models
│   ├── services/      # domain logic: accounts, auth, errors, journal, ledger, reports, parties, items, invoices, estimates, bills, budgets, reconciliation, export
│   ├── routers/       # auth, accounts, journal, ledger, reports, parties, items, invoices, bills, budgets, reconciliation, estimates, export
│   ├── mcp/           # context.py (sessions + helpers), tools.py (19 tools + 2 resources + 3 prompts), server.py (build_server + HTTP auth)
│   └── seed/          # coa.py (standard COA, auto-seeded); demo.py (demo data via --seed)
├── static/            # vanilla JS SPA: index.html + app.css, i18n/ (per-language JSON dictionaries), js/ (api, ui, i18n, doclines, router) + js/pages/ (12 pages)
├── tests/
├── skills/            # AI skills shipped with the repo (use-aihelper, maintain-aihelper)
├── requirements.txt
├── pytest.ini
├── pyrightconfig.json
├── .gitignore
├── README.md
├── AIHelper.md        # this project knowledge base
└── AI_WORKFLOW.md     # how the AI built the project
```

Layering: `routers → services → models (SQLAlchemy) → SQLite`. The frontend SPA is a hash-routed ES-module app that calls REST `/api/*` endpoints via fetch (session cookie sent automatically). The MCP server is a second entry point (`mcp_server.py`) that exposes the same services as typed MCP tools — it calls the services directly (never the routers), so both front doors share one domain implementation.

### Critical files

| File | Role |
| --- | --- |
| `main.py` | uvicorn runner; `--host`/`--port`/`--seed` (`--seed` calls `seed_demo_data()` before startup) |
| `mcp_server.py` | MCP entry: stdio by default; `--http` (requires `MCP_HTTP_TOKEN`), `--host`/`--port`, `--print-config <client>` |
| `app/main.py` | `create_app()` factory: `init_db()`, domain-exception handlers (404/409), all routers, `/api/health`, static SPA mount at `/` |
| `app/database.py` | SQLite engine (`accounting.db` at root, `ACCOUNTING_DB_PATH` override), WAL pragmas, `Base`/`SessionLocal`/`get_db`, `init_db` (tables + `ALTER TABLE` guard + COA seed) |
| `app/seed/coa.py` | 26-account standard COA, auto-seeded idempotently by `init_db` |
| `app/seed/demo.py` | `seed_demo_data()` for `--seed` (idempotent demo business) |
| `tests/conftest.py` | temp-DB env var; `app_client` (anonymous) + `client` (authenticated admin) fixtures |

### Established conventions (follow these in new code)

- **Layering**: routers are thin (parse/validate via Pydantic, call service, return ORM object); all domain logic lives in `services/`; services raise `NotFoundError`/`ConflictError`/`ValidationError` from `app/services/errors.py`, mapped to 404/409/422 by handlers registered in `create_app()`.
- **Journal posting**: `services/journal.py::create_journal_entry(db, *, date, description, lines, source_type='manual', source_id=None)` is the ONLY way entries are created; every financial event posts through it. It validates each account exists (404) + is active (409) and that `sum(debits) == sum(credits)` (else `ValidationError` 422). Void = a reversing entry (swapped debit/credit, `"VOID: "` prefix, `source_type='void'`, `source_id=original.id`); the original is flagged `is_voided`/`voided_by_id`. Never delete history.
- **Auth**: single user. First run → `POST /api/auth/setup` (creates user, sets cookie). All routers except `auth` require `Depends(get_current_user)`. Password: `pbkdf2_hmac` sha256, 200k iterations, stored as `{iterations}${salt}${digest}`. Session: itsdangerous `TimestampSigner` with per-user secret, cookie `session` (httponly, samesite=lax, 12h max age).
- **Models**: SQLAlchemy 2.0 typed style (`Mapped`, `mapped_column`), `DateTime(timezone=True)` + `server_default=func.now()`, enums stored as VARCHAR (`native_enum=False`). New models must be exported from `app/models/__init__.py` (required for `init_db` table creation).
- **Date fields**: annotate `datetime.date` (with `import datetime`) in both models and schemas — a bare `date: date | None = None` in a class body binds `date = None` before the annotation is evaluated → `TypeError`.
- **Schemas**: Pydantic v2, `ConfigDict(from_attributes=True)` on read models, `Field` constraints for validation (validation errors → 422 automatically).
- **COA**: 26 standard accounts auto-seeded on startup (idempotent, keyed by number). System accounts (`is_system=True`: Cash 1000, AR 1100, AP 2000, Taxes Payable 2200, Tax Recoverable 2210, Owner's Capital 3000, Retained Earnings 3900, Sales Revenue 4000, COGS 5000) cannot be deactivated. Subtypes used for lookups: `cash` (bank_kind `checking`), `ar`, `ap`, `tax`, `revenue`, `cogs`, `retained_earnings`, `capital`.
- **Tests**: `tests/conftest.py` sets `ACCOUNTING_DB_PATH` to a temp file before app import; `app_client` fixture = fresh DB + anonymous TestClient; `client` fixture = `app_client` + admin user (`admin`/`admin123`) with session cookie. New API tests use `client` (authenticated) or `app_client` (anonymous).

### Domain rules

**Ledger & statements**

- Ledger/report services read from journal lines; the single posting path guarantees every entry balances, so balances are internally consistent.
- Net balances are **debit-positive cents** (`debits - credits`); trial balance shows each account in its natural column.
- `general_ledger` opening balance = all activity strictly before `date_from`; `include_voided=False` hides voided entries **and their reversing entries together**, keeping the running balance accurate.
- Statement categorization uses `Account.type`; amounts are positive in the account type's natural direction (assets/expenses debit-normal, others credit-normal).
- Balance sheet equity includes **all-time unclosed net income** (no closing entries exist), which is what makes Assets = Liabilities + Equity hold by construction.

**Invoices & estimates**

- Documents post through the single journal path with provenance: invoice create → `source_type="invoice"`, payment → `source_type="invoice_payment"`, both with `source_id=invoice.id`.
- Posting accounts are fixed standard COA numbers via `get_account_by_number`: AR `1100`, Cash `1000`, Sales Revenue `4000`, Taxes Payable `2200`. No per-document overrides.
- Tax: flat `tax_rate` percent per document; `tax_cents` computed with `Decimal` + `ROUND_HALF_UP` (money stays integer cents). Zero tax → the tax line is **omitted** (a zero line would violate the debit-XOR-credit CHECK).
- Invoice lines: `{item_id?, description, quantity (≥1), unit_price_cents}`; `amount_cents` computed server-side; `item_id` optional, description falls back to the item name (snapshot on the line — item edits never rewrite history).
- Invoice status is **derived** (`is_voided` + `paid_cents` vs `total_cents` → `open`/`partially_paid`/`paid`/`void`), not stored.
- Void: only while `paid_cents == 0` (409 otherwise); voids the original posting via `void_journal_entry` (reversal). No refund flows.
- Estimates post **nothing** to the ledger; `convert` creates the invoice (today's date) and marks the estimate `converted` (409 on re-convert).

**Bills & AP**

- Provenance: bill create → `source_type="bill"`, payment → `source_type="bill_payment"`, both with `source_id=bill.id`.
- Fixed posting accounts: AP `2000`, Cash `1000`, Tax Recoverable `2210`.
- **Per-line expense account** (the one intentional deviation from the fixed-account convention): each `BillLine` carries a required `expense_account_id`, validated to exist (404), be `EXPENSE`-type (422), and be active (409). One Dr journal line per bill line.
- Create posts Dr Expense (per line) / Dr Tax Recoverable (omitted when tax = 0) / Cr AP (total incl. tax); payment posts Dr AP / Cr Cash.
- Bill status is **derived** exactly like invoices; void only while `paid_cents == 0`.
- `invoices.tax_cents(subtotal_cents, tax_rate)` is the shared public tax helper (Decimal + `ROUND_HALF_UP`), used by invoices, estimates, and bills.

**Budgets**

- Budgets are **planning data**: a planned amount for one account over `budget_start`/`budget_end` (CHECK `start <= end`). They post nothing and have no journal linkage, so they are freely updatable/deletable. No uniqueness constraint — overlapping budgets per account are allowed.
- **Report rule**: `GET /api/budgets/report?start=&end=` lists budgets **fully contained** in `[start, end]` (optionally filtered by `account_id`); each row compares the budget to actual activity over **that budget's own range** (no partial-overlap ambiguity).
- Actuals are shown in the account's **natural direction** (reusing `ledger.account_balance` — same convention as the statements).
- `variance_cents = budget_cents - actual_cents` (positive = under budget); `within_budget = actual_cents <= budget_cents`.
- Router declares `GET /report` **before** `GET /{budget_id}` so "report" is not captured as an id.

**Reconciliation**

- **Bank accounts** are accounts with `bank_kind` set (not by name/number). `GET /api/reconciliation/accounts` lists them with their current net balance; reconciling a non-bank account → 422.
- A `Reconciliation` matches a bank statement (date + ending balance) against journal lines. On create it **locks** those lines: `cleared=True` + `reconciliation_id`. Already-cleared line → 409; line from another account → 422; line dated after the statement date → 422; unknown line → 404.
- **Difference rule (classic)**: `opening` = account net activity strictly before the earliest cleared line's date; `cleared_total` = Σ(debit − credit) of cleared lines; `difference = statement_balance − (opening + cleared_total)`; `is_balanced = difference == 0`. Opening/cleared/difference are **stored** (immutable snapshot).
- **Correction path**: `DELETE /api/reconciliation/{id}` un-clears its lines and removes the record — no separate "unclear"/"void" state.
- **Void guard**: `void_journal_entry` refuses (409) an entry that has any cleared line.
- `general_ledger` lines expose `line_id` + `cleared` + `reconciliation_id` (the bank register is just the general ledger of a bank account; `line_id` is what the reconciliation UI submits to clear lines).
- `init_db` runs an `ALTER TABLE journal_lines ADD COLUMN` guard (via `PRAGMA table_info`) for `cleared`/`reconciliation_id` — `create_all` never alters existing tables; the guard is a no-op on fresh DBs.

**Export**

- Each `*_rows` builder in `services/export.py` reuses an existing report service and flattens it into `(title, subtitle, header, rows, filename)`; two generic renderers emit the file: `render_csv` (stdlib `csv`, LF, UTF-8) and `render_pdf` (ReportLab `SimpleDocTemplate` + `Table`, numeric columns right-aligned, header repeats per page).
- **Money in exports is dollars, 2 decimals** (`money(cents)` uses integer math, no float) — the one backend place cents become currency strings, alongside the UI boundary.
- **Endpoints**: `GET /api/export/{report}?format=csv|pdf` for `general-ledger` (requires `account_id`), `trial-balance`/`balance-sheet` (`as_of`), `income-statement`/`journal` (`date_from`/`date_to`), `invoices` (`customer_id`), `bills` (`vendor_id`); `include_voided` where applicable. Response is a `Response` with `Content-Disposition: attachment` (no Pydantic schema — the body is a file).
- **Frontend download**: the SPA does not `fetch` exports; `api.js::exportUrl(report, params)` builds the URL and the page sets `window.location.href` (attachment header + session cookie handle the rest).

**Frontend SPA**

- **No build step**: vanilla ES modules. `index.html` loads only `/js/router.js`; everything else is imported from there. Served by the FastAPI static mount at `/` (`html=True`).
- **Router** (`js/router.js`): hash-based (`#/route`); a `LOADERS` map lazily `import()`s each page module; an **auth gate** runs `GET /api/auth/me` before any non-login route (401 → `#/login`); `currentUser` cached, cleared on logout.
- **API wrapper** (`js/api.js`): one `request(method, path, body)` helper; the HttpOnly session cookie is sent automatically; non-2xx throws an `Error` whose `.message` is the server `detail`; `withQuery()` drops empty/undefined/null params.
- **Pages** (`js/pages/*.js`): each default-exports `{ render(container) }`; sets `container.innerHTML` then wires `addEventListener`s; forms use `novalidate` + client-side checks; server errors via `showFormError`; destructive actions confirm with `window.confirm` and report via `toast`.
- **Money & dates** (`js/ui.js`): all money is integer cents end-to-end; the UI types/reads **dollars**, converting with `dollarsToCents`/`centsToDollars` only at the form boundary; `fmtMoney`/`fmtDate`/`todayISO`; `esc()` HTML-escapes all interpolated values.
- **Shared line editor** (`js/doclines.js`): `createLineEditor({tbody, addBtn, items, expenseAccounts?, onTotal})` builds invoice/estimate/bill line rows (item auto-fills description+price, qty, unit price, live amount); bills pass `expenseAccounts` for the required per-line expense-account column.
- **Routes**: `login, dashboard, accounts, journal, ledger, statements, invoices, estimates, bills, budgets, reconciliation, export`.

**i18n (UI strings)**

- **Language/translation only (Phase 0)**: every user-facing UI string is externalized to per-language JSON dictionaries. Locale-aware currency/date formatting, API-error translation, and export-label translation are **postponed** (see below).
- **Dictionaries**: `static/i18n/{code}.json`, one per language. The browser consumes the `"ui"` section — flat `namespace.key -> string`. `en.json` is the baseline (259 keys, 17 namespaces: `app, nav, common, status, auth, dashboard, accounts, journal, ledger, statements, invoices, estimates, bills, budgets, reconciliation, export, doclines`). Thirty-nine languages exist so far: `en, fr, de, it, es, pt, sq, be, bg, ca, hr, fa, cs, da, et, fi, el, hu, is, ga, lv, lt, lb, mk, no, pl, ro, ru, sr, sl, sk, sv, uk, ar, hy, az, prs, ka, he` (`fa`, `ar`, `prs`, and `he` are RTL languages).
- **Core** (`js/i18n.js`): `t(key, vars)` looks up `ui.<key>`, substitutes `{var}` placeholders, and falls back to English then to the raw key. The `LANGS` registry (`{code, name, dir?}`) drives the language `<select>`. Detection order: `localStorage("lang")` → `navigator.languages` → `"en"`. `initI18n()` loads the active dictionary (await it before the first render); `setLang()` persists the choice, sets `<html lang/dir>`, and dispatches an `i18n:changed` document event.
- **Wiring**: `router.js` awaits `initI18n()` before the first render, wires the topbar `#lang-select`, and re-renders the current route on `i18n:changed`. Every page calls `t()` for user-facing strings; `statusBadge()` in `ui.js` resolves `status.<key>`; `export.js` resolves report names via a `labelKey` per report.
- **Adding a language**: create `static/i18n/{code}.json` with the same `ui` keys (and same `{placeholder}` sets) as `en.json`, then append `{code, name, dir?}` to `LANGS`. `tests/test_i18n.py` enforces key + placeholder parity across dictionaries, that every static `t("…")` literal and dynamic key family (nav routes, `statusBadge` values, account types, export label keys) exists in `en.json`, and that `LANGS` matches the dictionary files on disk.
- **Translation quality**: the same standard as README translations applies — fluent, natural phrasing in the target language, never word-for-word; technical terms kept in their original form; uncertain words verified via web search, never assumed. For short UI strings this means concise, idiomatic labels rather than literal renderings.
- **RTL**: `fa` (Persian) is the first RTL language. `applyHtmlAttrs()` sets `<html dir="rtl">` and now also runs on initial load (inside `initI18n()`), not only when the user switches language. `app.css` uses logical properties — `text-align: start` on `thead th`, `text-align: end` on `.num` and on inline action-cell styles — so the layout mirrors automatically under `dir="rtl"` (no `[dir="rtl"]` overrides). Any further RTL language needs only its dictionary + a `dir: "rtl"` `LANGS` entry.

**i18n — language queue (45 to add; target 84 total)**

Localization target is **84 languages**. Thirty-nine are done (`en, fr, de, it, es, pt, sq, be, bg, ca, hr, fa, cs, da, et, fi, el, hu, is, ga, lv, lt, lb, mk, no, pl, ro, ru, sr, sl, sk, sv, uk, ar, hy, az, prs, ka, he`); the 45 below are the authoritative queue — each will get a `static/i18n/{code}.json` dictionary + a `LANGS` entry, added in batches of ~3 in this listed order (the earlier "RTL last" rule was dropped — Persian already established the RTL layout). A language batch adds **only** the app dictionary + `LANGS` entry; the matching `README.{code}.md` is translated later in a separate README batch (same queue order). The user's requested list was curated: languages the model cannot translate reliably (low-resource, or sign languages) were dropped, and a country counts as "supported" only if it keeps at least one language (see README "Languages supported").

- **Middle East, Caucasus & Central Asia (9):** Kazakh `kk`, Kurdish `ku`, Kyrgyz `ky`, Maltese `mt`, Pashto `ps`, Tajik `tg`, Turkmen `tk`, Turkish `tr`, Uzbek `uz`
- **South Asia (7):** Bengali `bn`, Bhojpuri `bho`, Dzongkha `dz`, Hindi `hi`, Nepali `ne`, Tamil `ta`, Urdu `ur`
- **East & Southeast Asia (13):** Burmese `my`, Chinese (Mandarin) `zh`, Filipino `fil`, Indonesian `id`, Japanese `ja`, Khmer `km`, Korean `ko`, Lao `lo`, Malay `ms`, Mongolian `mn`, Sinhala `si`, Thai `th`, Vietnamese `vi`
- **Africa (12):** Amharic `am`, Chichewa `ny`, Hausa `ha`, Kinyarwanda `rw`, Malagasy `mg`, Shona `sn`, Somali `so`, Sesotho `st`, Swahili `sw`, Swazi `ss`, Xhosa `xh`, Zulu `zu`
- **Other (4):** Guaraní `gn`, Māori `mi`, Haitian Creole `ht`, Latin `la`

**Curation — excluded from the queue** (cannot be translated reliably; low-resource or sign languages): Tamazight/Amazigh, Mooré, Fulfulde, Sango, Tigrinya, Tigre, Oromo, Fijian, Bambara, Mauritian Creole, Seychellois Creole, Antiguan & Barbudan Creole, Bahamian Creole, Nahuatl, Marshallese, Nauruan, Palauan, Tok Pisin, Ndebele, Tetum, Tongan, Bislama, Sami, Dhivehi, Kirundi, Comorian, Quechua, Gilbertese, Tuvaluan, Samoan, Icelandic Sign Language, Korean Sign Language. Note: "Fiji Hindi" is covered by Hindi `hi`; "Mandarin" / "Standard Chinese" / "Mandarin Chinese" are all Chinese (Mandarin) `zh`.

**i18n — postponed (not yet built)**

- **Locale-aware money/date**: `fmtMoney` hardcodes `$` + `en-US` and `fmtDate` is plain ISO; switch to `Intl.NumberFormat`/`Intl.DateTimeFormat` keyed by the active language.
- **API error translation**: server `detail` strings are English; needs stable error codes + a client-side mapping table.
- **Export label translation**: PDF/CSV titles/headers are English; needs a `lang` query param threaded into `services/export.py`.
- **Plural rules**: CLDR plurals; v1 `t()` uses `{n}` interpolation with optional `_one`/`_other` key variants.

**README translations**

- **Convention**: one README per language at the repo root, `README.{code}.md` (`{code}` = the `LANGS` code); `README.md` is the English baseline. GitHub renders only the root `README.md`, so the others are alternate-language copies, not the default.
- **Translation quality (fluent, never word-for-word)**: translations must read as natural, fluent prose in the target language — a literal word-for-word rendering is a defect (it produces false friends and ungrammatical phrasing). The content stays intact: nothing added, nothing removed. Technical terms stay in their original form (e.g. `REST API`, `MCP`, `stdio`, `streamable HTTP`, `SPA`, `LLM`, `bearer token`), and domain terminology uses the target language's **standard accounting terms** (Persian: دفتر کل = general ledger, فهرست حساب‌ها = chart of accounts, ترازنامه = balance sheet, صورت سود و زیان = income statement, تراز آزمایشی = trial balance, حساب‌های دریافتنی/پرداختنی = AR/AP, پیش‌فاکتور = quote/estimate, دفتر روزنامه = journal, تنظیم حساب بانکی = bank reconciliation, مالیات قابل استرداد = tax recoverable, ابطال = void, بدهکار/بستانکار = debit/credit). When a word's translation is uncertain, **verify it via web search — never assume**. `README.fa.md` was revised to this standard on 2026-10-03 (its first draft read as a word-for-word translation).
- **Switcher**: each README carries a generated language-switcher block between `<!-- readme-switcher:start -->` / `<!-- readme-switcher:end -->` markers (a `<details>` + 4-column table of native-language names, current language bolded, `en` → `README.md`). The block lists only READMEs that exist on disk (not all `LANGS` entries), so a language batch (dictionary + `LANGS` only) leaves it unchanged. Regenerate with `.venv\Scripts\python.exe scripts\update_readme_switcher.py` after adding/removing a `README.{code}.md` — never hand-edit the block.
- **Parity**: `tests/test_readme_i18n.py` enforces that every `README.{code}.md` code is in `LANGS`, the switcher block is byte-identical to the script output, and each translation structurally matches English (same heading-level sequence, identical code blocks, identical external-URL set).
- **Status**: 2 of 84 done (`en`, `fa`); 82 queued. **Decoupled from the app-dictionary language batches** (decision #26): README translations happen in their own separate batches, later, following the same queue order (RTL — Hebrew/Arabic — last). `README.fa.md` (Persian, the first translation) follows GitHub's TOC anchor rules (lowercase; ZWNJ/combining marks/punctuation stripped; spaces → hyphens).

**Demo seed**

- `app/seed/demo.py::seed_demo_data()` is the `--seed` entry point; `main.py` calls it **before** `create_app()`, so it calls `init_db()` itself.
- **Idempotent**: a marker customer (`Acme Corporation`) guards the seed; the demo user `demo`/`demo123` is created only when no user exists.
- **Relative dates** anchor data to the current month (clamped to today), so statements and budget reports always show recent activity.
- **Everything posts through the services** (single posting path → seeded books balance by construction); line items pass explicit `unit_price_cents`.
- **Seeded mix**: 3 customers, 3 vendors, 5 items, 4 manual entries, 5 invoices covering all four statuses, 1 open estimate, 4 bills, 4 budgets, and 1 **balanced Cash reconciliation** (clears all Cash lines on/before the last day of the previous month; statement balance = actual net → `difference_cents == 0`).

**MCP server**

- **Tools wrap services, never duplicate logic**: every tool in `app/mcp/tools.py` calls the existing domain services (single posting path for writes), so the MCP server and the web app can never disagree. Tools are plain `def` with typed params (the SDK reflects the input schema from the hints) and docstrings that read like public API docs — the LLM's only guidance.
- **Surface**: 12 read tools (always registered) + 7 write tools (only when `MCP_ALLOW_WRITE=1`, read at `build_server()` call time so tests can toggle via monkeypatch) + 2 resources (`accounting://accounts`, `accounting://trial-balance`) + 3 prompts (`monthly_report`, `tax_position`, `cash_position`), registered by `build_server()` in `app/mcp/server.py`.
- **Per-call sessions**: `context.get_session()` opens one `SessionLocal()` per tool call (the protocol is stateless), commits on success, rolls back + closes in `finally`.
- **Errors are tool errors, never JSON-RPC errors**: `@context.safe_tool` converts `NotFoundError`/`ConflictError`/`ValidationError` into `ToolError` (→ `is_error=True` result the model reads and recovers from); resolvers raise `ToolError` listing the valid options.
- **Dual money fields**: `context.with_usd()` recursively walks every tool result and adds `<key>_usd` (via `services.export.money`) beside every `*_cents` int and known unsuffixed cents key, so small models can quote exact dollars.
- **References accept number or name**: `resolve_account` (exact number, else case-insensitive name), `resolve_customer`/`resolve_vendor` (case-insensitive name) — the name lookups live in the MCP layer because the services are id-based.
- **Transports & auth**: `mcp_server.py` → stdio by default; `--http` requires `MCP_HTTP_TOKEN` (refuses to start without it), binds `127.0.0.1:8765` by default, and wires `StaticTokenVerifier` + `AuthSettings` (issuer = resource URL = `http://{host}:{port}/mcp`) → 401 + RFC 9728 discovery for remote clients. `--print-config <client>` prints ready-to-paste configs for lmstudio/claude-code/claude-desktop/cursor/ollmcp/qwen-code/opencode.
- **SDK**: Python MCP SDK **v2** (`mcp>=2`, `MCPServer` — not legacy FastMCP); plain `def` tools run in a thread pool (sync SQLAlchemy is fine); the return type annotation is the output schema (return plain dicts/lists, no Pydantic output models); `ToolError` from `mcp.server.mcpserver.exceptions`.
- **Testing**: `tests/test_mcp_server.py` uses the SDK in-memory pattern — `Client(build_server(), raise_exceptions=True)` over anyio/asyncio against a fresh demo-seeded DB.

## Scope

Deliberately out of scope: payroll, QBO sync, Stripe, OCR, nonprofit, multi-company, job costing. In scope: accounts, customers, vendors, items, invoices, estimates, payments, bills, journal, bank register + reconciliation, reports, budgets, tax, auth, seed data, MCP access.

## Decision Log

| # | Decision | Rationale |
| --- | --- | --- |
| 1 | App is AI-written; that framing is the main deliverable | User's stated primary goal |
| 2 | Full-featured scope (double-entry + invoices + AR/AP + budgets + export) | User choice |
| 3 | Web app (FastAPI + vanilla JS), not CLI/GUI | User choice |
| 4 | SQLite + SQLAlchemy 2.0 | User choice; ACID for accounting data |
| 5 | AI attribution via README + AI_WORKFLOW.md | User choice |
| 6 | Integer cents for all money values | Avoid float precision errors in accounting |
| 7 | Seed script with demo accounts/transactions | App must demo well on first run |
| 8 | FastAPI over Flask | Modern, typed, auto OpenAPI docs |
| 9 | No existing OSS app adopted; SlowBooks-Pro-2026 studied as architecture reference only (source-available license bars code reuse) | GitHub search found no complete+web+Python+SQLite match |
| 10 | Auth: simple single-user login (setup on first run, signed cookie session) | User choice; good demo value, low complexity |
| 11 | Tax + estimates: include simple versions (flat tax rate per invoice/bill; estimate convert-to-invoice) | User choice; keeps scope complete |
| 12 | Currency: USD | User choice for public portfolio demo |
| 13 | Standard COA auto-seeded on every startup (idempotent), not only via `--seed` | App must be usable on first run; `--seed` adds demo transactions on top |
| 14 | Domain exceptions (`NotFoundError`/`ConflictError`) raised in services, mapped to HTTP by app-level handlers | Keeps services framework-free; one mapping point |
| 15 | Every non-auth router carries `Depends(get_current_user)` at router level | Uniform protection, explicit per router |
| 16 | Bills: per-line expense account (each `BillLine` requires `expense_account_id`, validated as an active EXPENSE account) | Unlike invoices (fixed revenue account 4000), a bill can be for any expense type |
| 17 | Budgets: custom date range per budget; report compares each budget to actuals over its own range, only for budgets fully contained in the queried window; actuals shown in the account's natural direction | Custom ranges give flexibility; the fully-contained rule avoids partial-overlap ambiguity; natural-direction actuals match the statements convention |
| 18 | Reconciliation: classic difference rule; cleared lines locked to their reconciliation; delete un-clears; void blocked on entries with cleared lines; `init_db` runs an `ALTER TABLE` guard for the new `journal_lines` columns | Locking + void guard keep reconciliations consistent with journal history; the guard preserves pre-existing databases since `create_all` never alters tables |
| 19 | Demo seed: idempotent (marker-customer guard); demo user `demo`/`demo123` only when no user exists; dates relative to the current month; all data posted through the normal services; Cash reconciled to a balanced state | `--seed` must be safe to run repeatedly; relative dates keep statements/budgets current; posting through services guarantees the seeded books balance by construction |
| 20 | MCP: Python SDK v2 (`MCPServer`, not legacy FastMCP); curated 19 intent-oriented tools (12 read + 7 write) instead of API passthrough; tools separated from transport; write tools gated behind `MCP_ALLOW_WRITE=1`; HTTP mode requires `MCP_HTTP_TOKEN` + loopback bind; dual money fields (cents + USD) in every tool result; errors returned in tool results, not JSON-RPC errors | Stateless MCP spec fits per-call sessions; accounting prior art (Intuit 145-tool passthrough vs Xero/community ~29-tool curated) favors curated tools for LLM reliability; LM Studio hosts MCP natively for local Qwen (Ollama needs an ollmcp bridge); financial data justifies token auth |
| 21 | i18n: per-language JSON dictionaries (`static/i18n/{code}.json`) with a flat `ui` section + a `t()` helper in `js/i18n.js`; English baseline first, then ~5 languages per batch (RTL last); language/translation separated from locale-aware currency/date, API-error, and export-label translation (all postponed) | The vanilla SPA has no i18n and no build step, so plain JSON dictionaries + a small `t()` fit the stack; `tests/test_i18n.py` enforces key/placeholder parity so a new language can't drift; separating concerns keeps each phase small and independently testable |
| 22 | RTL layout established with Persian (`fa`), pulled ahead of the "RTL last" plan: `applyHtmlAttrs()` runs on initial load (inside `initI18n()`, not only on language switch); `app.css` uses logical properties (`text-align: start` on `thead th`, `text-align: end` on `.num` and inline action cells) so the layout mirrors under `dir="rtl"` with no `[dir="rtl"]` overrides | Doing RTL once with a real language validates the approach and makes the remaining RTL languages (Hebrew, Arabic) trivial — a dictionary + a `dir:"rtl"` `LANGS` entry; logical properties keep the CSS direction-agnostic and DRY |
| 23 | README translations: one `README.{code}.md` per language at the repo root (`README.md` = English baseline); a generated language-switcher block (`scripts\update_readme_switcher.py`, between `readme-switcher:start/end` markers); `tests/test_readme_i18n.py` enforces code∈LANGS + switcher sync + structural parity with English | GitHub renders only the root `README.md`, so per-language files are alternate copies; the generated switcher + parity test keep 84 READMEs consistent without manual maintenance; the root layout (user's choice) is simpler than subfolders or a single multilingual file |
| 24 | Translation batch size: ~3 languages per batch (reduced from ~5), applied to both the app dictionaries and the README translations | User request; smaller batches keep each AI step reviewable and independently test-green |
| 25 | Translation quality: fluent, natural prose in the target language — never word-for-word; content intact (nothing added/removed); technical terms kept in original form; standard accounting terminology of the target language; uncertain words verified via web search, never assumed. `README.fa.md` revised to this standard (2026-10-03) | The first `README.fa.md` draft read as a word-for-word translation (user feedback): false friends (کلید for "ledger", نقل‌قول for "quote") and literal phrasing made it read off; fluent prose with correct domain terms is the quality bar for all README + i18n translations |
| 26 | Batch scope split: a language batch adds **only the app translation** (`static/i18n/{code}.json` + `LANGS` entry); README translations (`README.{code}.md` + switcher regeneration) are deferred to their own separate batches, later, in the same queue order (RTL last) | User request (2026-10-04): keeps each AI step small and independently testable, and lets the README prose — a larger, quality-sensitive artifact — be handled on its own cadence without slowing the 84-language app-localization rollout |
| 27 | i18n queue ordering: drop the "RTL last" rule — continue the queue in its listed regional order; RTL languages get `dir: "rtl"` in their `LANGS` entry but are no longer deferred to the end of the queue | Persian `fa` already established and validated the RTL layout (decision #22), so deferring RTL languages no longer serves a purpose — adding an RTL language is now trivial (a dictionary + a `dir:"rtl"` entry). User request (2026-10-09). Supersedes the "RTL last" ordering noted in decisions #21/#26. |
| 28 | Dev workflow: adopt the `open-codebase-index` opencode plugin for semantic code navigation — embeddings from Google's Gemma embedding model (`embeddinggemma-2`, 768 dims) served locally via LM Studio; auto-index + file watcher; per-project index in `.opencode/index/` (gitignored); plugin + embedding config live in global opencode config (`~/.opencode/opencode.json`, `~/.config/opencode/codebase-index.json`), not in this repo | Complements `AIHelper.md` ("what is this project and what rules govern it") with "where is this behavior implemented?" lookups (semantic search, definition lookup, call graph); keeps all inference local, consistent with the project's local-model premise; the index is a rebuildable artifact, so nothing index-related needs to be committed. Installed + verified 2026-10-09. |

## Environment & Tooling Notes

- **venv**: `.venv` at project root (Python 3.12.10). Recreate with `py -3.12 -m venv .venv` then `.venv\Scripts\python.exe -m pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt`. Pinned via `.python-version` (`3.12`). Run everything with `.venv\Scripts\python.exe` (e.g. `.venv\Scripts\python.exe -m pytest`).
- **pip mirror**: `pypi.org` is unreachable from this machine (timeouts). Install with `-i https://mirrors.aliyun.com/pypi/simple/` (verified working).
- **LSP**: opencode's pyright LSP needs the venv — configured via `pyrightconfig.json` (`venvPath`/`venv`) and the gitignored local `opencode.jsonc`. If the LSP reports unresolved third-party imports (sqlalchemy, pytest, fastapi...), **restart opencode** so it reloads config; the code is fine if pytest passes.
- **Run app**: `.venv\Scripts\python.exe main.py` → http://127.0.0.1:8000 (OpenAPI docs at `/docs`). First API use requires `POST /api/auth/setup`.
- **Run tests**: `.venv\Scripts\python.exe -m pytest -v` (208 tests).
- **Run MCP server**: `.venv\Scripts\python.exe mcp_server.py` (stdio) or `MCP_HTTP_TOKEN=... .venv\Scripts\python.exe mcp_server.py --http` (streamable HTTP at `http://127.0.0.1:8765/mcp`); `--print-config <client>` prints ready-to-paste client configs.
- **Type check**: `.venv\Scripts\python.exe -m pyright app` — keep it at 0 errors.
- **DB file**: `accounting.db` (+ `-wal`/`-shm` sidecars) at project root, gitignored. Tests use a temp DB via `ACCOUNTING_DB_PATH`.
- **Semantic index (open-codebase-index plugin)**: opencode plugin giving the AI semantic search over the repo. Embeddings via LM Studio — Google Gemma embedding model `text-embedding-embeddinggemma-2`, 768 dimensions, `http://127.0.0.1:1234/v1` — with auto-index + file watcher. Per-project index at `.opencode/index/` (gitignored, rebuildable via `index_codebase`); plugin registered globally in `~/.opencode/opencode.json`, embedding config in `~/.config/opencode/codebase-index.json` (neither is in this repo). Tools: `index_status` (readiness), `codebase_search` (semantic), `codebase_peek` (metadata only), `implementation_lookup` (definitions), `call_graph`/`call_graph_path` (call relationships), `codebase_context`/`architecture_context` (repo orientation), `find_similar` (duplicates), `code_communities`/`pr_impact` (module boundaries/blast radius), `index_health_check` (stale cleanup). Verified working 2026-10-09: 1,012 chunks, semantic scores 0.95–1.00.

## Known Limitations

- No frontend unit tests yet (validated via `node --check` + a TestClient smoke script).
- No audit logging yet (planned pattern: SQLAlchemy `after_flush` hooks).

## AI Instructions

- The build is complete; any new work is post-build (features, fixes, polish) and should follow the same "small steps, tests green after each step" rhythm.
- Follow the established conventions section exactly (layering, error handling, auth dependency, typed models, test fixtures).
- For codebase navigation, prefer the open-codebase-index tools over blind grep: `codebase_search` for behavior-level questions, `implementation_lookup` for known symbols, `call_graph` for callers/callees; fall back to `grep` for exact/exhaustive literal matches.
- Treat this document as the target design; verify against actual code — when code and this document disagree, update this document to match verified code.
- Keep the AI-authorship framing intact in any docs the AI writes.
- Run tests (`.venv\Scripts\python.exe -m pytest`) and keep them green after changes.
- Update this document (via the maintain-aihelper skill) when architecture changes or a feature is completed.
- Do not commit unless the user asks.

## Quick Project Facts

- Language/runtime: Python 3.12.10 (Windows, pwsh)
- Working dir: `D:\Projects\Python\GithubResume\Accounting`
- Parent dir `GithubResume` implies this is a GitHub portfolio project
- DB file: `accounting.db` at project root (WAL mode)
- Test suite: 208 tests, all passing (build complete + i18n Phase 0 + README i18n)

## Metadata

- Last Updated: 2026-10-09
- Last Full Scan: 2026-09-22 (full inventory of implemented app/ + tests/ for Phase 0–2 handoff)
- Last Incremental Update: 2026-10-09 (open-codebase-index semantic search plugin installed + verified: Gemma embeddinggemma-2 768-dim embeddings via LM Studio, auto-index + watcher, `.opencode/index/` gitignored; tooling note + navigation instruction + decision #28 added)
- Files Analyzed: `~/.config/opencode/codebase-index.json`, `~/.opencode/opencode.json`, `.opencode/index/` (index status), `AI_WORKFLOW.md`, `AIHelper.md`, `.gitignore`
- Git Commit: `861b1a0` (branch `main`, tracking `origin/main` at `git@github.com:Parsa-Mah/ai-accounting.git`)
- Architecture Version: 0.15 (RTL layout: `dir` applied on initial load + logical `text-align` in CSS/inline; RTL languages `fa`, `ar`, `prs`, `he`)
- AIHelper Version: 20 (open-codebase-index plugin: semantic search tooling documented; no app architecture change)
