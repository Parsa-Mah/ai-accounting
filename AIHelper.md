# AIHelper — Accounting

## Project Summary

Python accounting web application (double-entry bookkeeping core + invoicing, AR/AP, budgets, CSV/PDF export). The project exists to demonstrate that a **local AI model writes the entire application** — the app is the vehicle, AI authorship is the product.

## Project Goals

1. Primary: a complete, working accounting app authored 100% by AI (no human-written code).
2. Secondary: a real, coherent accounting domain implementation (not a toy).
3. Public presentation: README + `AI_WORKFLOW.md` must make AI authorship explicit (model, runtime, hardware).

## Current Project Status (build in progress)

All 12 phases (0–11) of the build plan are **complete and tested** (167/167 tests green). The build is finished.

| File / Dir | State |
| --- | --- |
| `main.py` | uvicorn runner with `--host`, `--port`, `--seed` flags (`--seed` calls `app.seed.demo.seed_demo_data()` before the app starts) |
| `app/main.py` | `create_app()` factory: `init_db()`, domain-exception handlers (404/409), router includes (auth, accounts, journal, ledger, reports, parties, items, invoices, bills, budgets, reconciliation, estimates, export), `/api/health`, static mount (serves the `static/` SPA at `/` with `html=True`) |
| `app/database.py` | SQLite engine (`accounting.db` at root, overridable via `ACCOUNTING_DB_PATH` env var), WAL pragmas (`journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`, `foreign_keys=ON`), `Base`, `SessionLocal` (`expire_on_commit=False`), `get_db`, `init_db` (creates tables + `ALTER TABLE` guard adding `cleared`/`reconciliation_id` to a pre-existing `journal_lines` + seeds COA) |
| `app/models/` | `Account` (+ `AccountType` enum), `User`, `JournalEntry` + `JournalLine` (CHECK debit-XOR-credit, provenance `source_type`/`source_id`, `is_voided`/`voided_by_id`, `cleared`/`reconciliation_id`), `Customer`/`Vendor`, `Item`, `Invoice` + `InvoiceLine` + `InvoicePayment`, `Estimate` + `EstimateLine`, `Bill` + `BillLine` (per-line `expense_account_id`) + `BillPayment`, `Budget` (account + date range + `budget_cents`), `Reconciliation` (account + statement date/balance + stored opening/cleared/difference) |
| `app/schemas/` | Pydantic v2: `AccountCreate/Update/Read`, `Credentials/AuthStatus/AuthUser`, `JournalEntryCreate/Read`, `JournalLineCreate/Read`, `GeneralLedgerRead`/`TrialBalanceRead`, `IncomeStatementRead`/`BalanceSheetRead`/`StatementLineRead`, `Customer/Vendor Create/Read`, `ItemCreate/Update/Read`, `InvoiceCreate/PayCreate/Read` + line/payment reads, `EstimateCreate/Read`, `BillCreate/PayCreate/Read` + line/payment reads (line carries required `expense_account_id`), `BudgetCreate/Update/Read` + `BudgetReportRead` (rows + totals), `ReconciliationCreate/Read` + `BankAccountRead` |
| `app/services/` | `accounts.py` (CRUD + deactivate + journal-line guard + `get_account_by_number`), `auth.py` (pbkdf2 hashing, itsdangerous signed cookies), `journal.py` (single posting path `create_journal_entry` + void-as-reversal), `ledger.py` (`account_balance`, `general_ledger` running balance, `trial_balance`), `reports.py` (`income_statement`, `balance_sheet`), `parties.py` (customer/vendor CRUD), `items.py` (item CRUD + deactivate), `invoices.py` (create+post, pay, void; public `tax_cents` helper shared by estimates/bills), `estimates.py` (create, convert-to-invoice), `bills.py` (create+post, pay, void), `budgets.py` (CRUD + `budget_report` actual-vs-budget/variance), `reconciliation.py` (bank accounts, create/get/list/delete reconciliation, cleared-line locking), `export.py` (7 report row builders + `render_csv`/`render_pdf` renderers + `money` cents→dollars helper), `errors.py` (`NotFoundError`→404, `ConflictError`→409, `ValidationError`→422) |
| `app/routers/` | `auth.py` (public), `accounts.py` + `journal.py` + `ledger.py` + `reports.py` + `parties.py` + `items.py` + `invoices.py` + `bills.py` + `budgets.py` + `reconciliation.py` + `estimates.py` + `export.py` (7 CSV/PDF download endpoints) (auth-protected) |
| `app/dependencies.py` | `get_current_user` — cookie session check, 401 if missing/invalid/no user |
| `app/seed/coa.py` | 26-account standard COA, auto-seeded idempotently on every startup via `init_db` |
| `app/seed/demo.py` | `seed_demo_data()` for `main.py --seed`: idempotent demo business (demo user, 3 customers, 3 vendors, 5 items, 4 manual entries, 5 invoices in all 4 statuses, 4 bills, 1 estimate, 4 budgets, 1 balanced Cash reconciliation) |
| `tests/` | `conftest.py` (temp-DB env var, `app_client` anonymous + `client` authenticated fixtures), `test_health.py`, `test_accounts.py`, `test_auth.py`, `test_journal.py`, `test_ledger.py`, `test_reports.py`, `test_parties_items.py`, `test_invoices.py`, `test_estimates.py`, `test_bills.py`, `test_budgets.py`, `test_reconciliation.py`, `test_export.py`, `test_demo_seed.py` — **167 tests, all passing** |
| `requirements.txt` | fastapi, uvicorn[standard], SQLAlchemy 2.0, pydantic v2, itsdangerous, reportlab, pytest, httpx, pyright |
| `pytest.ini` | filters 2 third-party deprecation warnings |
| `pyrightconfig.json` | pins pyright to `.venv` (LSP needs opencode restart to pick up) |
| `static/` | Vanilla JS SPA (no build step, ES modules): `index.html` + `app.css` (tab shell), `js/api.js` (fetch wrapper, cookies auto-sent), `js/ui.js` (money/date/escape/toast helpers), `js/doclines.js` (shared invoice/estimate/bill line editor), `js/router.js` (hash router, lazy page imports, auth gate), `js/pages/*.js` (login, dashboard, accounts, journal, ledger, statements, invoices, estimates, bills, budgets, reconciliation, export) |
| `AI_WORKFLOW.md` | Public record of how the AI built the project phase by phase (Phase 11) |

Git: branch `main`, tracking `origin/main` (GitHub: `Parsa-Mah/ai-accounting`). All phases 0–11 implemented; Phases 0–10 committed and pushed (HEAD `572a965`); **Phase 11 (seed + docs) is implemented but uncommitted**.

## Build Roadmap (approved plan — use as the work queue)

Small steps, 1–2 files each, `pytest` green after every step. All 12 phases (0–11) are done — the build is complete.

| # | Phase | Status |
| --- | --- | --- |
| 0 | Foundation: requirements/venv, `database.py`, app factory + runner, test scaffolding | **Done** |
| 1 | Chart of accounts: model, schema, service, router, tests, standard COA auto-seed | **Done** |
| 2 | Auth: single-user setup/login/logout/me, pbkdf2 + signed cookie, route protection | **Done** |
| 3 | **Journal (the core)**: `models/journal.py` (entry + lines, CHECK constraint debit-XOR-credit, provenance `source_type`/`source_id`), `services/journal.py` (single posting path `create_journal_entry` + void-as-reversing-entry), schemas, router, tests (balance, exclusivity, void) | **Done** |
| 4 | Ledger + statements: `services/ledger.py` (balances, general ledger, trial balance), `services/reports.py` (income statement, balance sheet), router, tests (A = L + E identity) | **Done** |
| 5 | Parties, items, estimates, invoices (AR + tax): `models/party.py` (Customer, Vendor) + `models/item.py`, `models/invoice.py` + `models/estimate.py`, `services/invoices.py` (create posts Dr AR incl. tax / Cr Revenue / Cr Tax Payable; payment Dr Cash / Cr AR; void), `services/estimates.py` (convert-to-invoice), routers, tests | **Done** |
| 6 | Bills (AP + tax): `models/bill.py`, `services/bills.py` (Dr Expense / Dr Tax Recoverable / Cr AP; payment Dr AP / Cr Cash; void), router, tests | **Done** |
| 7 | Budgets: `models/budget.py`, `services/budgets.py` (actual vs budget, variance), router, tests | **Done** |
| 8 | Bank register + reconciliation: `cleared`/`reconciliation_id` on journal lines, `services/reconciliation.py`, router, tests | **Done** |
| 9 | Frontend SPA: `static/index.html` + `app.css` (tab shell), `static/js/api.js` + `router.js` (hash-routed, lazy page imports), one page per step: login, dashboard, accounts, journal, ledger, statements, invoices, estimates, bills, budgets, reconciliation, export (placeholder) | **Done** |
| 10 | Export: CSV service + router, PDF (ReportLab) + router, tests — 7 reports (general ledger, trial balance, income statement, balance sheet, journal, invoices, bills) as CSV/PDF downloads | **Done** |
| 11 | Seed + polish: `app/seed/demo.py` + wire `--seed` flag, `AI_WORKFLOW.md`, README status update, full test run | **Done** |

### Ledger & statements conventions (Phase 4, implemented)

- Ledger/report services read from journal lines; the single posting path guarantees every entry balances, so balances are internally consistent.
- Net balances are **debit-positive cents** (`debits - credits`). Trial balance shows each account in its natural column (positive net → debit column).
- `general_ledger` opening balance = all activity strictly before `date_from` (0 when no `date_from`). `include_voided=False` hides voided entries **and their reversing entries together** (the pair nets to zero), keeping the running balance accurate.
- Statement categorization uses `Account.type` (asset/liability/equity/revenue/expense); `subtype` aids lookups (e.g. `retained_earnings`, `revenue`, `cogs`).
- Statement amounts are positive in the account type's natural direction (assets/expenses debit-normal, others credit-normal).
- Balance sheet equity includes **all-time unclosed net income** (no closing entries exist), which is what makes Assets = Liabilities + Equity hold by construction.
- Voided entries are offset by their reversing entries, so net balances are correct without filtering.

### Invoices & estimates conventions (Phase 5, implemented)

- Documents post through the single journal path with provenance: invoice create → `source_type="invoice"`, payment → `source_type="invoice_payment"`, both with `source_id=invoice.id`.
- Posting accounts are fixed standard COA numbers looked up via `get_account_by_number`: AR `1100`, Cash `1000`, Sales Revenue `4000`, Taxes Payable `2200`. No per-document account overrides.
- Tax: flat `tax_rate` percent per document; `tax_cents` computed with `Decimal` + `ROUND_HALF_UP` (money stays integer cents). Zero tax → the tax line is **omitted** (a zero line would violate the debit-XOR-credit CHECK).
- Invoice lines: `{item_id?, description, quantity (≥1), unit_price_cents}`; `amount_cents = quantity × unit_price_cents` computed server-side. `item_id` optional; description falls back to the item name (snapshot on the line — item edits never rewrite history).
- Invoice status is **derived** (`is_voided` + `paid_cents` vs `total_cents` → `open`/`partially_paid`/`paid`/`void`), not stored.
- Void: only while `paid_cents == 0` (409 otherwise); voids the original posting via `void_journal_entry` (reversal), sets `is_voided`/`voided_by_entry_id`. No refund flows.
- `Invoice.entry_id` is nullable in the DB only transiently (invoice is flushed to get its id before its entry exists); always set in the same transaction.
- Estimates post **nothing** to the ledger; `convert` creates the invoice (today's date) and marks the estimate `converted` (409 on re-convert).
- **Date annotation trap**: in class bodies (SQLAlchemy models *and* Pydantic schemas), annotate date fields as `datetime.date` (`import datetime`). `date: date | None = None` evaluates the default first, binding `date = None` before the annotation is evaluated → `TypeError`.

### Bills & AP conventions (Phase 6, implemented)

- Documents post through the single journal path with provenance: bill create → `source_type="bill"`, payment → `source_type="bill_payment"`, both with `source_id=bill.id`.
- Posting accounts are fixed standard COA numbers looked up via `get_account_by_number`: AP `2000`, Cash `1000`, Tax Recoverable `2210`.
- **Per-line expense account** (the one intentional deviation from the fixed-account convention): each `BillLine` carries a required `expense_account_id`; validated to exist (404), be an `EXPENSE`-type account (422), and be active (409, via the journal path). One Dr journal line per bill line, described `"<description> (expense)"`.
- Create posts Dr Expense (per line) / Dr Tax Recoverable (omitted when tax = 0) / Cr AP (total incl. tax); payment posts Dr AP / Cr Cash.
- Bill status is **derived** exactly like invoices (`open`/`partially_paid`/`paid`/`void`); void only while `paid_cents == 0` (409 otherwise).
- `invoices.tax_cents(subtotal_cents, tax_rate)` is the shared public tax helper (Decimal + `ROUND_HALF_UP`), used by invoices, estimates, and bills.

### Budgets conventions (Phase 7, implemented)

- Budgets are **planning data**: a `Budget` is a planned amount for one account over a custom `budget_start`/`budget_end` date range (CHECK `start <= end`). They post **nothing** to the ledger and have no journal linkage, so they are freely updatable/deletable (unlike journal history). No uniqueness constraint — overlapping budgets per account are allowed.
- Any account type may be budgeted. The report expresses each account's actual in its **natural direction** (expense/asset = debit-normal `debits - credits`; revenue/liability/equity = credit-normal `credits - debits`), reusing `ledger.account_balance` — the same convention as the statements.
- **Report rule**: `GET /api/budgets/report?start=&end=` lists budgets **fully contained** in `[start, end]` (`budget_start >= start AND budget_end <= end`), optionally filtered by `account_id`. Each row compares the budget amount to actual activity over **that budget's own range** — so querying a whole year is an annual review and querying a month is a monthly view, with no partial-overlap ambiguity.
- `variance_cents = budget_cents - actual_cents` (positive = under budget / below plan); `within_budget = actual_cents <= budget_cents`.
- Router declares `GET /report` **before** `GET /{budget_id}` so "report" is not captured as an id.

### Reconciliation conventions (Phase 8, implemented)

- **Bank accounts** are accounts with `bank_kind` set (not by name/number). `GET /api/reconciliation/accounts` lists them with their current net balance. Reconciling a non-bank account → 422.
- A `Reconciliation` matches a bank statement (date + ending balance) against a set of journal lines. On create it **locks** those lines: `cleared=True` + `reconciliation_id` set. A line already cleared → 409; a line from another account → 422; a line dated after the statement date → 422; unknown line → 404.
- **Difference rule (classic)**: `opening` = account net activity strictly before the earliest cleared line's date; `cleared_total` = Σ(debit − credit) of the cleared lines; `difference = statement_balance − (opening + cleared_total)`. Non-zero difference = outstanding items; `is_balanced = difference == 0`. Opening/cleared/difference are **stored** so the record is an immutable snapshot.
- **Correction path**: `DELETE /api/reconciliation/{id}` un-clears its lines (`cleared=False`, `reconciliation_id=NULL`) and removes the record — there is no separate "unclear" or "void" state.
- **Void guard**: `void_journal_entry` refuses (409) an entry that has any cleared line, so a cleared line can never be reversed out from under a reconciliation.
- `general_ledger` lines expose `line_id` + `cleared` + `reconciliation_id` (the bank register is just the general ledger of a bank account; `line_id` is what the reconciliation UI submits to clear lines — added in Phase 9 since `create_reconciliation` needs journal line ids).
- **Schema migration**: `create_all` never alters existing tables, so `init_db` runs an `ALTER TABLE journal_lines ADD COLUMN` guard (via `PRAGMA table_info`) for `cleared`/`reconciliation_id`. No-op on fresh DBs; preserves data on pre-Phase-8 DBs.

### Export conventions (Phase 10, implemented)

- **Reports as tables**: each `*_rows` builder in `services/export.py` reuses an existing report service (`ledger.general_ledger`/`trial_balance`, `reports.income_statement`/`balance_sheet`, `journal.list_journal_entries`, `invoices.list_invoices`, `bills.list_bills`) and flattens it into `(title, subtitle, header, rows, filename)` where `rows` are lists of strings. Two generic renderers then emit the file: `render_csv` (stdlib `csv`, LF endings, UTF-8) and `render_pdf` (ReportLab `SimpleDocTemplate` + `Table`, numeric columns right-aligned, header repeats per page).
- **Money in exports is dollars, 2 decimals** (`money(cents)` uses integer math, no float) — the one backend place cents become currency strings, alongside the UI boundary.
- **Endpoints**: `GET /api/export/{report}?format=csv|pdf` for `general-ledger` (requires `account_id`), `trial-balance`/`balance-sheet` (`as_of`), `income-statement`/`journal` (`date_from`/`date_to`), `invoices` (`customer_id`), `bills` (`vendor_id`); each also takes `include_voided` where applicable. The response is a `Response` with `Content-Disposition: attachment; filename="..."` (no Pydantic schema — the body is a file, not JSON).
- **Frontend download**: the SPA does not `fetch` exports; `api.js::exportUrl(report, params)` builds the URL and the page sets `window.location.href` to it. The attachment header makes the browser save the file without navigating away; the session cookie is sent automatically.

### Frontend conventions (Phase 9, implemented)

- **No build step**: vanilla HTML/CSS/JS as ES modules. `index.html` loads only `/js/router.js` (a `<script type="module">`); everything else is imported from there. Served by the FastAPI static mount at `/` (`html=True`), so `/` returns `index.html`.
- **Router** (`js/router.js`): hash-based (`#/route`). A `LOADERS` map lazily `import()`s each page module (code splitting); a missing page renders a "still being built" placeholder. An **auth gate** runs `GET /api/auth/me` before any non-login route and bounces to `#/login` on 401. `currentUser` is cached to avoid re-fetching on every nav; logout clears it.
- **API wrapper** (`js/api.js`): one `request(method, path, body)` helper; `fetch` sends the HttpOnly session cookie automatically (same-origin). Non-2xx throws an `Error` whose `.message` is the server `detail` (string, or joined FastAPI validation `msg`s). A `withQuery()` helper drops empty/undefined/null params.
- **Pages** (`js/pages/*.js`): each default-exports `{ render(container) }`. They set `container.innerHTML` to a template, then wire up `addEventListener`s. Forms use `novalidate` + client-side checks and surface server errors via `showFormError`. Destructive actions confirm with `window.confirm` and report via `toast`.
- **Money & dates** (`js/ui.js`): all money is integer cents end-to-end; the UI types/reads **dollars** and converts with `dollarsToCents`/`centsToDollars` (only at the form boundary). `fmtMoney` renders cents as USD; `fmtDate`/`todayISO` handle ISO dates; `esc()` HTML-escapes all interpolated values.
- **Shared line editor** (`js/doclines.js`): `createLineEditor({tbody, addBtn, items, expenseAccounts?, onTotal})` builds the invoice/estimate/bill line rows (optional item auto-fills description+price, qty, unit price, live amount). Bills pass `expenseAccounts` to add the required per-line expense-account column. Returns `{ addLine, lines, totals, update }`.
- **Routes**: `login, dashboard, accounts, journal, ledger, statements, invoices, estimates, bills, budgets, reconciliation, export`. The `export` page is a report picker (7 reports, conditional account/date/party fields, CSV/PDF) that builds a download URL via `api.js::exportUrl` and sets `window.location.href`.
- **No frontend unit tests yet**; validated via `node --check` (syntax) + a TestClient smoke script that exercises every page's data path + static assets (45 checks). A "wiring audit" test (every endpoint has an SPA caller) is a possible Phase 9 follow-up.

### Demo seed conventions (Phase 11, implemented)

- `app/seed/demo.py::seed_demo_data()` is the `--seed` entry point; `main.py` calls it **before** `create_app()`, so it calls `init_db()` itself (tables + COA).
- **Idempotent**: a marker customer (`Acme Corporation`) guards the seed — if present, it prints a message and exits without changes. Safe to run repeatedly.
- **Demo user**: `demo` / `demo123`, created via `setup_user` only when no user exists (an existing user is never touched).
- **Relative dates**: helpers `_first_of_month(offset)` / `_end_of_month(offset)` / `_on(month_offset, day)` (clamped to today) anchor data to the current month, so statements and budget reports always show recent activity regardless of when the seed runs.
- **Everything posts through the services** (`create_invoice`, `pay_invoice`, `void_invoice`, `create_bill`, `pay_bill`, `create_estimate`, `create_budget`, `create_journal_entry`) — the single posting path guarantees the seeded books balance by construction. Line items pass explicit `unit_price_cents` (the API never pulls prices from items).
- **Seeded mix**: 3 customers, 3 vendors, 5 items; 4 manual entries (owner capital, equipment, 2× monthly rent); 5 invoices covering all four statuses (paid, partially_paid, open, void) + 1 open estimate; 4 bills (2 paid, 2 open, per-line expense accounts); 4 budgets (3 current-month, 1 previous-month).
- **Balanced reconciliation**: clears **all** Cash lines dated on/before the last day of the previous month and sets the statement balance to the account's actual net balance at that date → `difference_cents == 0`, `is_balanced`.

## Architecture

Stack: Python 3.12 · FastAPI + uvicorn · SQLAlchemy 2.0 · SQLite (`accounting.db`) · vanilla HTML/CSS/JS SPA frontend (no build step, Phase 9) · ReportLab (PDF export) · pytest + TestClient.

```
Accounting/
├── main.py            # entry point: uvicorn runner (+ --seed flag)
├── app/
│   ├── main.py        # FastAPI app factory, mounts, DB init, exception handlers
│   ├── database.py    # engine, session, schema init, COA seed hook
│   ├── dependencies.py# get_current_user (cookie session auth)
│   ├── models/        # Account, AccountType, User, JournalEntry, JournalLine, Customer, Vendor, Item, Invoice, Estimate, Bill, Budget, Reconciliation
│   ├── schemas/       # Pydantic v2 request/response models
│   ├── services/      # domain logic: accounts, auth, errors, journal, ledger, reports, parties, items, invoices, estimates, bills, budgets, reconciliation, export
│   ├── routers/       # auth, accounts, journal, ledger, reports, parties, items, invoices, bills, budgets, reconciliation, estimates, export
│   └── seed/          # coa.py (standard COA, auto-seeded); demo.py (demo data via --seed)
├── static/            # vanilla JS SPA (Phase 9): index.html + app.css, js/ (api, ui, doclines, router) + js/pages/ (12 pages)
├── tests/
├── skills/            # AI skills shipped with the repo (use-aihelper, maintain-aihelper)
├── requirements.txt
├── pytest.ini
├── pyrightconfig.json
├── .gitignore
├── README.md
├── AIHelper.md        # this project knowledge base
└── AI_WORKFLOW.md     # how the AI built the project (Phase 11)
```

Layering: `routers → services → models (SQLAlchemy) → SQLite`. The frontend SPA (Phase 9) is a hash-routed ES-module app that calls REST `/api/*` endpoints via fetch (session cookie sent automatically).

### Established conventions (follow these in new code)

- **Layering**: routers are thin (parse/validate via Pydantic, call service, return ORM object); all domain logic lives in `services/`; services raise `NotFoundError`/`ConflictError`/`ValidationError` from `app/services/errors.py`, mapped to 404/409/422 by handlers registered in `create_app()`.
- **Journal posting**: `services/journal.py::create_journal_entry(db, *, date, description, lines, source_type='manual', source_id=None)` is the ONLY way entries are created; every financial event posts through it. It validates each account exists (404) + is active (409) and that `sum(debits) == sum(credits)` (else `ValidationError` 422). Void = a reversing entry (swapped debit/credit, `"VOID: "` prefix, `source_type='void'`, `source_id=original.id`); the original is flagged `is_voided`/`voided_by_id`. Never delete history.
- **Auth**: single user. First run → `POST /api/auth/setup` (creates user, sets cookie). All routers except `auth` require `Depends(get_current_user)`. Password: `pbkdf2_hmac` sha256, 200k iterations, stored as `{iterations}${salt}${digest}`. Session: itsdangerous `TimestampSigner` with per-user secret, cookie `session` (httponly, samesite=lax, 12h max age).
- **Models**: SQLAlchemy 2.0 typed style (`Mapped`, `mapped_column`), `DateTime(timezone=True)` + `server_default=func.now()`, enums stored as VARCHAR (`native_enum=False`). New models must be exported from `app/models/__init__.py` (required for `init_db` table creation). When a column shares a name with a type (e.g. a `date` column), `import datetime` and annotate `Mapped[datetime.date]` — a bare `Mapped[date]` in a class body trips pyright's self-reference check.
- **Schemas**: Pydantic v2, `ConfigDict(from_attributes=True)` on read models, `Field` constraints for validation (validation errors → 422 automatically).
- **COA**: 26 standard accounts auto-seeded on startup (idempotent, keyed by number). System accounts (`is_system=True`: Cash 1000, AR 1100, AP 2000, Taxes Payable 2200, Tax Recoverable 2210, Owner's Capital 3000, Retained Earnings 3900, Sales Revenue 4000, COGS 5000) cannot be deactivated. Subtypes used for lookups: `cash` (bank_kind `checking`), `ar`, `ap`, `tax`, `revenue`, `cogs`, `retained_earnings`, `capital`.
- **Tests**: `tests/conftest.py` sets `ACCOUNTING_DB_PATH` to a temp file before app import; `app_client` fixture = fresh DB + anonymous TestClient; `client` fixture = `app_client` + admin user (`admin`/`admin123`) with session cookie. New API tests use `client` (authenticated) or `app_client` (anonymous).

### Domain invariants

- Every journal entry must balance: sum(debits) == sum(credits).
- Money is stored as **integer cents** end-to-end (no floats); convert to currency only at API/UI boundaries. Currency: **USD**.
- Invoice posting auto-generates journal entries (Dr AR incl. tax / Cr Revenue / Cr Tax Payable; payment: Dr Cash / Cr AR).
- Bill posting: Dr Expense / Dr Tax Recoverable / Cr AP; payment: Dr AP / Cr Cash.
- Balance sheet must satisfy Assets = Liabilities + Equity (incl. retained earnings).
- Tax: simple flat rate per invoice/bill (decided: include simple versions of tax + estimates).

## Reference Architecture (studied, NOT copied)

Searched GitHub for existing open-source Python accounting apps; none matched all needs (complete + web + Python + SQLite). Closest: **SlowBooks-Pro-2026** (FastAPI + SQLAlchemy 2.0 + vanilla JS + SQLite — near-identical stack, but **source-available license → no code reuse**) and **koalixcrm** (best fully-OSS option, Django, SQLite-capable). Decision: study SlowBooks as a blueprint only. Clone at `D:\Projects\Python\GithubResume\SlowBooks-Pro-2026` (shallow, outside this repo).

Patterns worth adopting (implement our own versions):

- **Single posting path**: one `create_journal_entry(db, date, description, lines, source_type, source_id)` service is the ONLY way journal entries are created; every financial event (invoice, bill, payment, bank txn) posts through it, guaranteeing sum(debits) == sum(credits).
- **DB-level guard**: CHECK constraint on lines — each line is debit-only OR credit-only, never both.
- **Provenance**: `source_type`/`source_id` polymorphic columns on the entry header trace every journal entry back to its originating document.
- **Void = reversing entry**: swap debit/credit, prefix "VOID:", carry all dimensions; never delete history.
- **Money discipline**: we keep our own decision: integer cents (not Decimal/Numeric).
- **Audit**: SQLAlchemy `after_flush` hooks auto-log changes (not yet implemented — fold into Phase 3+ if feasible, else note as limitation).
- **SQLite tuning**: `PRAGMA journal_mode=WAL`, `busy_timeout=5000`, `synchronous=NORMAL` — **done** in `app/database.py`.
- **Bank reconciliation**: `cleared` + `reconciliation_id` on ledger lines; `bank_kind` on accounts (not names/numbers) keys the register — `bank_kind` column **done** on Account.
- **Frontend**: hash-routed SPA; one JS module per page exporting `render()`; central `api.js` wrapper; a "wiring audit" test fails if an endpoint has no SPA caller (Phase 9).

Status as of Phase 11 (build complete): single posting path, DB-level debit-XOR-credit guard, provenance columns, void-as-reversal, ledger, financial statements, invoices/estimates, bills, budgets, bank reconciliation, CSV/PDF export, frontend SPA, and the demo seed are **implemented**; audit logging remains the only pending reference-architecture pattern.

Scope difference: our app is smaller — skip payroll, QBO sync, Stripe, OCR, nonprofit, multi-company, job costing. Keep: accounts, customers, vendors, items, invoices, estimates, payments, bills, journal, bank register + reconciliation, reports, budgets, tax, audit, auth, seed data.

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
| 13 | Standard COA auto-seeded on every startup (idempotent), not only via `--seed` | App must be usable on first run; `--seed` (Phase 11) adds demo transactions on top |
| 14 | Domain exceptions (`NotFoundError`/`ConflictError`) raised in services, mapped to HTTP by app-level handlers | Keeps services framework-free; one mapping point |
| 15 | Every non-auth router carries `Depends(get_current_user)` at router level | Uniform protection, explicit per router |
| 16 | Bills: per-line expense account (each `BillLine` requires `expense_account_id`, validated as an active EXPENSE account) | Unlike invoices (fixed revenue account 4000), a bill can be for any expense type; per-line accounts are needed for correct expense categorization |
| 17 | Budgets: custom date range per budget; report compares each budget to actuals over its own range, only for budgets fully contained in the queried window; actuals shown in the account's natural direction | Custom ranges give flexibility (monthly/quarterly/annual); the fully-contained rule avoids partial-overlap ambiguity; natural-direction actuals match the statements convention |
| 18 | Reconciliation: classic difference rule (statement balance − (opening before first cleared line + cleared lines)); cleared lines locked to their reconciliation; delete un-clears; void blocked on entries with cleared lines; `init_db` runs an `ALTER TABLE` guard for the new `journal_lines` columns | Classic rule makes cleared lines meaningful (non-zero difference = outstanding items); locking + void guard keep reconciliations consistent with journal history; the guard preserves pre-Phase-8 databases since `create_all` never alters tables |
| 19 | Demo seed: idempotent (marker-customer guard, skip if present); creates demo user `demo`/`demo123` only when no user exists; dates relative to the current month (clamped to today); all data posted through the normal services; Cash reconciled to a balanced state as of the last day of the previous month | App must demo well on first run (decision 7); idempotency makes `--seed` safe to run repeatedly; relative dates keep statements/budgets current whenever the seed runs; posting through services guarantees the seeded books balance by construction |

## Environment & Tooling Notes

- **venv**: `.venv` at project root (Python 3.12.10). Recreate with `py -3.12 -m venv .venv` then `.venv\Scripts\python.exe -m pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt`. Pinned via `.python-version` (`3.12`). Run everything with `.venv\Scripts\python.exe` (e.g. `.venv\Scripts\python.exe -m pytest`).
- **pip mirror**: `pypi.org` is unreachable from this machine (timeouts). Install with `-i https://mirrors.aliyun.com/pypi/simple/` (verified working).
- **LSP**: opencode's pyright LSP needs the venv — configured via `pyrightconfig.json` (`venvPath`/`venv`) and `opencode.jsonc` (`lsp.pyright.initialization.python.pythonPath`). If the LSP reports unresolved third-party imports (sqlalchemy, pytest, fastapi...), **restart opencode** so it reloads config; the code is fine if pytest passes.
- **Run app**: `.venv\Scripts\python.exe main.py` → http://127.0.0.1:8000 (OpenAPI docs at `/docs`). First API use requires `POST /api/auth/setup`.
- **Run tests**: `.venv\Scripts\python.exe -m pytest -v` (162 tests as of this update).
- **Type check**: `.venv\Scripts\python.exe -m pyright app` (pyright is installed in the venv and listed in `requirements.txt`; `pyrightconfig.json` pins it to `.venv`). Keep it at 0 errors.
- **DB file**: `accounting.db` (+ `-wal`/`-shm` sidecars) at project root, gitignored. Tests use a temp DB via `ACCOUNTING_DB_PATH`.
- **opencode.jsonc** is gitignored (local-only) and now contains the pyright venv config.

## Known Limitations

- No frontend unit tests yet (validated via `node --check` + a TestClient smoke script); a "wiring audit" test (every endpoint has an SPA caller) is a possible follow-up.
- No audit logging yet (planned pattern: SQLAlchemy `after_flush` hooks).

## AI Instructions

- The build roadmap above is complete (all 12 phases Done). Any new work should follow the same "small steps, tests green after each step" rhythm and the conventions below.
- Follow the established conventions section exactly (layering, error handling, auth dependency, typed models, test fixtures).
- Treat this document as the target design; verify against actual code — when code and this document disagree, update this document to match verified code.
- Keep the AI-authorship framing intact in any docs the AI writes.
- Run tests (`.venv\Scripts\python.exe -m pytest`) and keep them green after changes.
- Update this document (via the maintain-aihelper skill) at phase boundaries, especially the Build Roadmap status column.
- Do not commit unless the user asks.

## Quick Project Facts

- Language/runtime: Python 3.12.10 (Windows, pwsh)
- Working dir: `D:\Projects\Python\GithubResume\Accounting`
- Parent dir `GithubResume` implies this is a GitHub portfolio project
- DB file: `accounting.db` at project root (WAL mode)
- Test suite: 167 tests, all passing (Phases 0–11, build complete)

## Metadata

- Last Updated: 2026-09-25
- Last Full Scan: 2026-09-22 (full inventory of implemented app/ + tests/ for Phase 0–2 handoff)
- Last Incremental Update: 2026-09-25 (Phase 11 seed + polish: `app/seed/demo.py` (idempotent demo business, demo user, balanced reconciliation), `tests/test_demo_seed.py` (5 tests), `AI_WORKFLOW.md` (public build record), README finalized (status, features, run instructions; Python 3.12). 167 tests green + pyright 0 errors. Build complete. Prior: Phase 10 export)
- Files Analyzed: `app/seed/demo.py`, `tests/test_demo_seed.py`, `AI_WORKFLOW.md`, `README.md`, `main.py`, `app/database.py`, `app/services/{invoices,bills,estimates,auth,journal,reconciliation,ledger,reports}.py`, `app/models/{invoice,estimate,reconciliation}.py`, `app/schemas/{party,item,budget,invoice,bill,journal}.py`, `tests/conftest.py`
- Git Commit: `279befe` (branch `main`, tracking `origin/main` at `git@github.com:Parsa-Mah/ai-accounting.git`; all phases 0–11 committed)
- Architecture Version: 0.11 (build complete: foundation + accounts + auth + journal core + ledger/statements + invoices/estimates + bills + budgets + bank reconciliation + frontend SPA + CSV/PDF export + demo seed + AI_WORKFLOW.md)
- AIHelper Version: 2 (added Build Roadmap handoff section, conventions, environment notes)
