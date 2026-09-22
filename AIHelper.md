# AIHelper — Accounting

## Project Summary

Python accounting web application (double-entry bookkeeping core + invoicing, AR/AP, budgets, CSV/PDF export). The project exists to demonstrate that a **local AI model writes the entire application** — the app is the vehicle, AI authorship is the product.

## Project Goals

1. Primary: a complete, working accounting app authored 100% by AI (no human-written code).
2. Secondary: a real, coherent accounting domain implementation (not a toy).
3. Public presentation: README + `AI_WORKFLOW.md` must make AI authorship explicit (model, runtime, hardware).

## Current Project Status (build in progress)

Phases 0–4 of the build plan are **complete and tested** (49/49 tests green). Phases 5–11 remain.

| File / Dir | State |
| --- | --- |
| `main.py` | uvicorn runner with `--host`, `--port`, `--seed` flags (`--seed` imports `app.seed.demo` — **not created yet, Phase 11**) |
| `app/main.py` | `create_app()` factory: `init_db()`, domain-exception handlers (404/409), router includes (auth, accounts, journal, ledger, reports), `/api/health`, static mount (skipped until `static/` exists) |
| `app/database.py` | SQLite engine (`accounting.db` at root, overridable via `ACCOUNTING_DB_PATH` env var), WAL pragmas (`journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`, `foreign_keys=ON`), `Base`, `SessionLocal` (`expire_on_commit=False`), `get_db`, `init_db` (creates tables + seeds COA) |
| `app/models/` | `Account` (+ `AccountType` enum), `User`, `JournalEntry` + `JournalLine` (CHECK debit-XOR-credit, provenance `source_type`/`source_id`, `is_voided`/`voided_by_id`) |
| `app/schemas/` | Pydantic v2: `AccountCreate/Update/Read`, `Credentials/AuthStatus/AuthUser`, `JournalEntryCreate/Read`, `JournalLineCreate/Read`, `GeneralLedgerRead`/`TrialBalanceRead`, `IncomeStatementRead`/`BalanceSheetRead`/`StatementLineRead` |
| `app/services/` | `accounts.py` (CRUD + deactivate + journal-line guard), `auth.py` (pbkdf2 hashing, itsdangerous signed cookies), `journal.py` (single posting path `create_journal_entry` + void-as-reversal), `ledger.py` (`account_balance`, `general_ledger` running balance, `trial_balance`), `reports.py` (`income_statement`, `balance_sheet`), `errors.py` (`NotFoundError`→404, `ConflictError`→409, `ValidationError`→422) |
| `app/routers/` | `auth.py` (public), `accounts.py` + `journal.py` + `ledger.py` + `reports.py` (auth-protected) |
| `app/dependencies.py` | `get_current_user` — cookie session check, 401 if missing/invalid/no user |
| `app/seed/coa.py` | 26-account standard COA, auto-seeded idempotently on every startup via `init_db` |
| `tests/` | `conftest.py` (temp-DB env var, `app_client` anonymous + `client` authenticated fixtures), `test_health.py`, `test_accounts.py`, `test_auth.py`, `test_journal.py`, `test_ledger.py`, `test_reports.py` — **49 tests, all passing** |
| `requirements.txt` | fastapi, uvicorn[standard], SQLAlchemy 2.0, pydantic v2, itsdangerous, reportlab, pytest, httpx, pyright |
| `pytest.ini` | filters 2 third-party deprecation warnings |
| `pyrightconfig.json` | pins pyright to `.venv` (LSP needs opencode restart to pick up) |
| `static/` | **does not exist yet** (Phase 9) |
| `AI_WORKFLOW.md` | **not written yet** (Phase 11) |

Git: branch `main`, tracking `origin/main` (GitHub: `Parsa-Mah/ai-accounting`). Phases 0–4 committed and pushed (HEAD `384cfd2`).

## Build Roadmap (approved plan — use as the work queue)

Small steps, 1–2 files each, `pytest` green after every step. Phases 0–4 done; continue from Phase 5.

| # | Phase | Status |
| --- | --- | --- |
| 0 | Foundation: requirements/venv, `database.py`, app factory + runner, test scaffolding | **Done** |
| 1 | Chart of accounts: model, schema, service, router, tests, standard COA auto-seed | **Done** |
| 2 | Auth: single-user setup/login/logout/me, pbkdf2 + signed cookie, route protection | **Done** |
| 3 | **Journal (the core)**: `models/journal.py` (entry + lines, CHECK constraint debit-XOR-credit, provenance `source_type`/`source_id`), `services/journal.py` (single posting path `create_journal_entry` + void-as-reversing-entry), schemas, router, tests (balance, exclusivity, void) | **Done** |
| 4 | Ledger + statements: `services/ledger.py` (balances, general ledger, trial balance), `services/reports.py` (income statement, balance sheet), router, tests (A = L + E identity) | **Done** |
| 5 | Parties, items, estimates, invoices (AR + tax): `models/party.py` (Customer, Vendor) + `models/item.py`, `models/invoice.py` + `models/estimate.py`, `services/invoices.py` (create posts Dr AR incl. tax / Cr Revenue / Cr Tax Payable; payment Dr Cash / Cr AR; void), `services/estimates.py` (convert-to-invoice), routers, tests | Next |
| 6 | Bills (AP + tax): `models/bill.py`, `services/bills.py` (Dr Expense / Dr Tax Recoverable / Cr AP; payment Dr AP / Cr Cash; void), router, tests | Pending |
| 7 | Budgets: `models/budget.py`, `services/budgets.py` (actual vs budget, variance), router, tests | Pending |
| 8 | Bank register + reconciliation: `cleared`/`reconciliation_id` on journal lines, `services/reconciliation.py`, router, tests | Pending |
| 9 | Frontend SPA: `static/index.html` + `app.css` (tab shell), `static/js/api.js` + `router.js` (hash-routed), then one page per step: login, dashboard, accounts, journal, ledger, statements, invoices/estimates, bills, budgets, export | Pending |
| 10 | Export: CSV service + router, PDF (ReportLab) + router, tests | Pending |
| 11 | Seed + polish: `app/seed/demo.py` + wire `--seed` flag, `AI_WORKFLOW.md`, README status update, full test run | Pending |

### Ledger & statements conventions (Phase 4, implemented)

- Ledger/report services read from journal lines; the single posting path guarantees every entry balances, so balances are internally consistent.
- Net balances are **debit-positive cents** (`debits - credits`). Trial balance shows each account in its natural column (positive net → debit column).
- `general_ledger` opening balance = all activity strictly before `date_from` (0 when no `date_from`). `include_voided=False` hides voided entries **and their reversing entries together** (the pair nets to zero), keeping the running balance accurate.
- Statement categorization uses `Account.type` (asset/liability/equity/revenue/expense); `subtype` aids lookups (e.g. `retained_earnings`, `revenue`, `cogs`).
- Statement amounts are positive in the account type's natural direction (assets/expenses debit-normal, others credit-normal).
- Balance sheet equity includes **all-time unclosed net income** (no closing entries exist), which is what makes Assets = Liabilities + Equity hold by construction.
- Voided entries are offset by their reversing entries, so net balances are correct without filtering.

## Architecture

Stack: Python 3.13 · FastAPI + uvicorn · SQLAlchemy 2.0 · SQLite (`accounting.db`) · vanilla HTML/CSS/JS frontend (no build step, Phase 9) · ReportLab (PDF, Phase 10) · pytest + TestClient.

```
Accounting/
├── main.py            # entry point: uvicorn runner (+ --seed flag, Phase 11)
├── app/
│   ├── main.py        # FastAPI app factory, mounts, DB init, exception handlers
│   ├── database.py    # engine, session, schema init, COA seed hook
│   ├── dependencies.py# get_current_user (cookie session auth)
│   ├── models/        # Account, AccountType, User (+ JournalEntry, JournalLine, Invoice, Bill, Budget ... in Phases 3-8)
│   ├── schemas/       # Pydantic v2 request/response models
│   ├── services/      # domain logic: accounts, auth, errors, journal, ledger, reports (+ invoices, bills, budgets, reconciliation ...)
│   ├── routers/       # auth, accounts, journal, ledger, reports (+ invoices, bills, budgets, export ...)
│   └── seed/          # coa.py (standard COA, auto-seeded); demo.py (Phase 11)
├── static/            # tabbed SPA (Phase 9): dashboard, accounts, journal, ledger, statements, invoices, bills, budgets, export
├── tests/
├── skills/            # AI skills shipped with the repo (use-aihelper, maintain-aihelper)
├── requirements.txt
├── pytest.ini
├── pyrightconfig.json
├── .gitignore
├── README.md
├── AIHelper.md        # this project knowledge base
└── AI_WORKFLOW.md     # to be written (Phase 11): how the AI built the project
```

Layering: `routers → services → models (SQLAlchemy) → SQLite`. Frontend (Phase 9) calls REST `/api/*` endpoints via fetch.

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

Status as of Phase 4: single posting path, DB-level debit-XOR-credit guard, provenance columns, void-as-reversal, ledger, and financial statements are **implemented**; audit logging and bank reconciliation remain pending.

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

## Environment & Tooling Notes

- **venv**: `.venv` at project root (Python 3.13.15). Run everything with `.venv\Scripts\python.exe` (e.g. `.venv\Scripts\python.exe -m pytest`).
- **pip mirror**: `pypi.org` is unreachable from this machine (timeouts). Install with `-i https://mirrors.aliyun.com/pypi/simple/` (verified working).
- **LSP**: opencode's pyright LSP needs the venv — configured via `pyrightconfig.json` (`venvPath`/`venv`) and `opencode.jsonc` (`lsp.pyright.initialization.python.pythonPath`). If the LSP reports unresolved third-party imports (sqlalchemy, pytest, fastapi...), **restart opencode** so it reloads config; the code is fine if pytest passes.
- **Run app**: `.venv\Scripts\python.exe main.py` → http://127.0.0.1:8000 (OpenAPI docs at `/docs`). First API use requires `POST /api/auth/setup`.
- **Run tests**: `.venv\Scripts\python.exe -m pytest -v` (49 tests as of this update).
- **Type check**: `.venv\Scripts\python.exe -m pyright app` (pyright is installed in the venv and listed in `requirements.txt`; `pyrightconfig.json` pins it to `.venv`). Keep it at 0 errors.
- **DB file**: `accounting.db` (+ `-wal`/`-shm` sidecars) at project root, gitignored. Tests use a temp DB via `ACCOUNTING_DB_PATH`.
- **opencode.jsonc** is gitignored (local-only) and now contains the pyright venv config.

## Known Limitations

- Phases 5–11 not implemented: no invoices, estimates, bills, budgets, reconciliation, frontend, export, or demo seed yet.
- `main.py --seed` references `app.seed.demo.seed_demo_data` which does not exist until Phase 11 (lazy import; app runs fine without the flag).
- No audit logging yet (planned pattern: SQLAlchemy `after_flush` hooks).

## AI Instructions

- The build roadmap above is the work queue; continue from the first non-Done phase. Keep the "small steps, tests green after each step" rhythm.
- Follow the established conventions section exactly (layering, error handling, auth dependency, typed models, test fixtures).
- Treat this document as the target design; verify against actual code — when code and this document disagree, update this document to match verified code.
- Keep the AI-authorship framing intact in any docs the AI writes.
- Run tests (`.venv\Scripts\python.exe -m pytest`) and keep them green after changes.
- Update this document (via the maintain-aihelper skill) at phase boundaries, especially the Build Roadmap status column.
- Do not commit unless the user asks.

## Quick Project Facts

- Language/runtime: Python 3.13.15 (Windows, pwsh)
- Working dir: `D:\Projects\Python\GithubResume\Accounting`
- Parent dir `GithubResume` implies this is a GitHub portfolio project
- DB file: `accounting.db` at project root (WAL mode)
- Test suite: 49 tests, all passing (Phases 0–4)

## Metadata

- Last Updated: 2026-09-22
- Last Full Scan: 2026-09-22 (full inventory of implemented app/ + tests/ for Phase 0–2 handoff)
- Last Incremental Update: 2026-09-22 (git-status sync after Phase 4 commit `384cfd2`; no source changes since the Phase 4 update)
- Files Analyzed: git state only (no source files changed since the Phase 4 update)
- Git Commit: `384cfd2` (branch `main`, tracking `origin/main` at `git@github.com:Parsa-Mah/ai-accounting.git`; Phases 0–4 committed and pushed)
- Architecture Version: 0.4 (foundation + accounts + auth + journal core + ledger/statements implemented)
- AIHelper Version: 2 (added Build Roadmap handoff section, conventions, environment notes)
