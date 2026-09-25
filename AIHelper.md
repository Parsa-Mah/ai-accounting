# AIHelper — Accounting

## Project Summary

Python accounting web application (double-entry bookkeeping core + invoicing, AR/AP, budgets, CSV/PDF export). The project exists to demonstrate that a **local AI model writes the entire application** — the app is the vehicle, AI authorship is the product.

## Project Goals

1. Primary: a complete, working accounting app authored 100% by AI (no human-written code).
2. Secondary: a real, coherent accounting domain implementation (not a toy).
3. Public presentation: README + `AI_WORKFLOW.md` must make AI authorship explicit (model, runtime, hardware).

## Current Project Status (build in progress)

Phases 0–11 of the build plan are **complete and tested** (167/167 tests green). **Phase 12 (MCP server) is fully researched and designed (see "Phase 12" section below) but not yet implemented** — a fresh session should pick it up from there.

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

Git: branch `main`, tracking `origin/main` (GitHub: `Parsa-Mah/ai-accounting`). All phases 0–11 implemented, committed, and pushed (HEAD `49a3c5c`). Phase 12 (MCP) is designed, not yet implemented.

## Build Roadmap (approved plan — use as the work queue)

Small steps, 1–2 files each, `pytest` green after every step. Phases 0–11 are done; **Phase 12 (MCP server) is the active work item** — design and research are complete in the section below.

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
| 12 | **MCP server**: `mcp_server.py` + `app/mcp/` (tools/resources/prompts on Python SDK v2), stdio + streamable-HTTP transports, gated write tools, in-memory client tests, README "Using with an AI" section | **Pending** (researched + designed 2026-09-25 — see below) |

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

### Phase 12: MCP server (researched + designed 2026-09-25 — IMPLEMENT THIS)

**Goal**: let any AI (ChatGPT, Claude, a local Qwen via LM Studio or Ollama) drive the app like an accountant — answer questions ("What was March's payroll?", "How much tax do we owe?", "Which invoices are overdue?") and, optionally, record transactions. The AI calls typed tools; the tools call the existing services (same single posting path — no logic duplication).

#### Research summary (web research done 2026-09-25 — do NOT redo, just build on this)

- **Current spec: 2026-07-28** (modelcontextprotocol.io/specification/2026-07-28). Key facts that shape the design:
  - Protocol is **stateless**: no sessions, no `initialize` handshake; every request carries protocol version + client capabilities in `_meta`. (Fits our per-call DB sessions perfectly.)
  - **MRTR** (multi round-trip requests) replaced server-initiated elicitation/sampling: a server returns `InputRequiredResult` (`resultType: "input_required"`) and the client retries with `inputResponses`.
  - **Roots, Sampling, Logging are DEPRECATED** — do not build on them (migration: pass paths via tool params; log to stderr).
  - **Structured tool output** is stable: `outputSchema` + `structuredContent` on tool results.
  - List/read results carry `ttlMs`/`cacheScope` caching hints; servers SHOULD return tools in deterministic order (prompt-cache hits).
  - **Streamable HTTP** is the only HTTP transport (old HTTP+SSE deprecated). stdio remains for local.
  - Remote auth: OAuth 2.1 + Client ID Metadata Documents (we use a simpler bearer token — see below).
- **Python SDK v2** (`pip install mcp` → 2.x; the old `FastMCP` is v1, legacy branch `v1.x`):
  - API: `from mcp.server import MCPServer`; `mcp = MCPServer("name")`; `@mcp.tool()`, `@mcp.resource("uri://...")`, `@mcp.prompt()` decorators.
  - **Type hints + docstrings become the JSON Schema** — no manual schema writing (this is the pattern to follow for every tool).
  - Speaks 2026-07-28 AND negotiates down to older clients automatically.
  - **Testing pattern (use this)**: in-memory client — `from mcp import Client; async with Client(mcp) as client: result = await client.call_tool("add", {...})` — no subprocess, no port. SDK examples use `@pytest.mark.anyio`.
  - CLI: `mcp dev server.py` (opens MCP Inspector), `mcp run server.py --transport streamable-http`. Install with `pip install "mcp[cli]"` (via the aliyun mirror — see Environment notes).
  - Docs: https://py.sdk.modelcontextprotocol.io/ (get-started, servers/tools, servers/structured-output, servers/resources, servers/prompts, run/asgi, run/authorization, testing).
- **Unreal Engine 5.8 "Unreal MCP"** (Experimental, shipped June 2026 — studied in depth from dev.epicgames.com docs):
  - First-party plugin embedding an MCP server inside the editor process; HTTP-only, loopback-only, **no auth**; server name `unreal-mcp`; default `http://127.0.0.1:8000/mcp`; auto-start option; serial tool execution on the game thread.
  - **Lesson 1 — Toolset Registry**: tool definitions are fully decoupled from the protocol layer. Toolsets are classes of typed functions with docstrings; a registry collects them; the MCP layer just wraps each function as a Tool. Docstrings/type hints are reflected into the schema "with the same care as the public surface of any other API".
  - **Lesson 2 — Tool-search mode** (default ON in UE): `tools/list` returns only 3 meta-tools (`list_toolsets`, `describe_toolset`, `call_tool`) so hundreds of tools don't blow up the LLM context. **Not needed at our scale** (~18 tools) — we advertise tools flat; revisit only if the count grows past ~25.
  - **Lesson 3 — `GenerateClientConfig`**: a command writes ready-made client config files (`.mcp.json` for ClaudeCode/Cursor/VSCode/Gemini, TOML for Codex) into the project root. We implement this as `--print-config <client>`.
  - UE's tool-authoring guidelines (adopted): keep functions small and focused (one tool, one responsibility); prefer structured return types over free-form strings; write docstrings like public API docs.
- **Ecosystem**: official registry registry.modelcontextprotocol.io (~9,700 servers); 6 official SDKs (Python, TS, C#, Java, Kotlin, Swift); **MCP Inspector** (`npx @modelcontextprotocol/inspector`) is the standard debugging client; "MCP Apps" (ext-apps) = UIs embedded in chat UIs, the newest direction. Major MCP-enabled apps: GitHub, Stripe, Notion, Linear, Sentry, Figma, Playwright, Cloudflare.
- **Accounting prior art (directly comparable — studied)**:
  - **Intuit QuickBooks official** (github.com/intuit/quickbooks-online-mcp-server): 145 tools, 29 entity types, full CRUD passthrough + 11 financial reports, OAuth 2.0. Exhaustive approach — context-heavy.
  - **Xero official** (github.com/XeroAPI/xero-mcp-server): 60+ tools (accounting, payments, payroll), OAuth2 or bearer token.
  - **Community curated** (github.com/d4m14ndx/xero-mcp-server): **29 curated tools** — "Drive your Xero accounting from Claude" (create invoices/bills, record payments, reconcile bank transactions).
  - **AgenticBooks** (github.com/AgenticBooks/agenticbooks-mcp): hosted remote MCP exposing a startup's ledger (live P&L, bank balances, transaction review, COA); every write audit-trailed and scoped to the caller.
  - **Consensus: curated, intent-oriented tools beat API passthrough for LLM reliability.** We follow the curated approach.
- **Local-model clients (verified 2026-09-25)**:
  - **LM Studio** (0.3.17+; current 0.4.x): full MCP host — `mcp.json` with local (stdio command/args) or remote (url) servers; works with local Qwen. Primary target for "local Qwen asks the books questions".
  - **Ollama is NOT an MCP client** — it's a model server with tool-calling support; it needs a bridge: `ollmcp` (TUI MCP client for Ollama — `ollmcp mcp add accounting -- python mcp_server.py`), or Cline / opencode / Claude Code pointed at Ollama as the model backend.
  - **Claude Desktop / Claude Code**: native MCP (stdio + HTTP). **ChatGPT**: remote MCP connectors (needs hosted HTTP endpoint). **OpenAI Agents SDK / Responses API** and **Anthropic Messages API**: native MCP connector support. **Qwen Code**: `mcpServers` in settings.json (HTTP preferred over SSE).

#### Design (approved 2026-09-25)

**File layout** (UE lesson: separate tool definitions from transport):

```
mcp_server.py            # entry point: argparse (transport, --port, --host, --print-config), calls build_server()
app/mcp/__init__.py      # empty
app/mcp/context.py       # get_session() context manager (SessionLocal per call), startup() = init_db(), money() re-export from services.export
app/mcp/tools.py         # all tool functions: typed params, docstring-described, service-backed
app/mcp/server.py        # build_server() -> MCPServer with tools/resources/prompts registered; reads MCP_ALLOW_WRITE at call time
tests/test_mcp_server.py # in-memory Client(mcp) tests (anyio)
```

**Core mechanics:**
- Built on **Python SDK v2**: add `mcp>=2` to `requirements.txt` (install via aliyun mirror).
- **Standalone process** opening the same SQLite file: `ACCOUNTING_DB_PATH` env var (default `accounting.db` at project root — see `app/database.py:10`). WAL mode + `busy_timeout=5000` (already in `app/database.py:19-24`) make concurrent web-app + MCP access safe.
- `build_server()` calls `init_db()` first (idempotent: tables + COA + ALTER guard).
- **Each tool call opens its own `SessionLocal()` session** (stateless, matches the 2026-07-28 protocol), commits on success, closes in `finally`.
- **Errors are returned in the tool result**, never as JSON-RPC errors: catch `NotFoundError`/`ConflictError`/`ValidationError` from `app/services/errors.py` and return a result with `isError=True` and a human-readable message (e.g. "Account 'Payroll' not found — use list_accounts to see valid accounts").
- **Dual money fields**: every money value in tool output appears as both `*_cents` (int) and a formatted USD string, reusing `app/services/export.py::money(cents)` (integer math, no float) — so small local models can quote numbers correctly.
- **Docstrings are the LLM's only guidance** (UE guideline): each tool docstring states what it does, when to use it, argument meanings, and an example question ("Use for questions like 'how much tax do we owe?'").
- Account references in tool params accept **number or name** (e.g. `"5200"` or `"Payroll Expense"`); resolve via `accounts.get_account_by_number` then a case-insensitive name lookup; unknown → error result listing valid options.

**Read tools (11) — always registered:**

| Tool | Signature (type hints = schema) | Backing service |
| --- | --- | --- |
| `list_accounts` | `() -> list[dict]` | `app/services/accounts.py` list — number, name, type, subtype, is_system, active |
| `get_income_statement` | `(month: str \| None = None) -> dict` (month = `"YYYY-MM"`) | `reports.income_statement(db, start, end)` |
| `get_balance_sheet` | `(as_of: str \| None = None) -> dict` (ISO date) | `reports.balance_sheet(db, as_of)` |
| `get_trial_balance` | `(as_of: str \| None = None) -> dict` | `ledger.trial_balance(db, as_of)` |
| `get_account_ledger` | `(account: str, date_from: str \| None = None, date_to: str \| None = None, include_voided: bool = False) -> dict` | `ledger.general_ledger(db, account_id, ...)` — running balance + lines |
| `search_transactions` | `(query: str \| None = None, account: str \| None = None, date_from: str \| None = None, date_to: str \| None = None, limit: int = 50) -> list[dict]` | **NEW service function** `ledger.search_transactions(db, ...)` — free-text LIKE on `JournalEntry.description` + `JournalLine.description`, filters, returns entry + line rows with account number/name, date, debit/credit cents |
| `list_invoices` | `(status: str \| None = None, month: str \| None = None) -> list[dict]` | `invoices.list_invoices(db)` — filter in Python (status is derived; month = issue-date) |
| `get_invoice` | `(invoice_id: int) -> dict` | `invoices.get_invoice(db, id)` |
| `list_bills` | `(status: str \| None = None, month: str \| None = None) -> list[dict]` | `bills.list_bills(db)` — filter in Python |
| `list_estimates` | `(status: str \| None = None) -> list[dict]` | `estimates.list_estimates(db)` |
| `get_budget_report` | `(start: str, end: str) -> dict` | `budgets.budget_report(db, start, end)` |
| `list_reconciliations` | `() -> list[dict]` | `reconciliation.list_reconciliations(db)` |

**Write tools (7) — registered ONLY when env `MCP_ALLOW_WRITE=1`** (read at `build_server()` call time, NOT import time, so tests can toggle via monkeypatch):

| Tool | Signature | Backing service |
| --- | --- | --- |
| `create_journal_entry` | `(date: str, description: str, lines: list[dict]) -> dict` — line = `{"account": str, "debit_cents": int, "credit_cents": int}` (one of debit/credit per line) | `journal.create_journal_entry` (resolve account refs) |
| `create_invoice` | `(customer: str, issue_date: str, lines: list[dict], tax_rate: float = 0.0, due_date: str \| None = None) -> dict` — line = `{"description": str, "quantity": int, "unit_price_cents": int}` | `invoices.create_invoice` (resolve customer by name) |
| `pay_invoice` | `(invoice_id: int, amount_cents: int, date: str \| None = None, method: str = "cash") -> dict` | `invoices.pay_invoice` |
| `void_invoice` | `(invoice_id: int, reason: str \| None = None) -> dict` | `invoices.void_invoice` |
| `create_bill` | `(vendor: str, due_date: str, lines: list[dict], tax_rate: float = 0.0) -> dict` — line = `{"description": str, "quantity": int, "unit_price_cents": int, "expense_account": str}` | `bills.create_bill` (resolve vendor + per-line expense account) |
| `pay_bill` | `(bill_id: int, amount_cents: int, date: str \| None = None, method: str = "cash") -> dict` | `bills.pay_bill` |
| `create_budget` | `(account: str, budget_start: str, budget_end: str, amount_cents: int) -> dict` | `budgets.create_budget` |

All writes go through the existing services → single posting path → books balance by construction. Service validation errors (unbalanced entry, unknown customer, void-with-payments) surface as `isError` tool results.

**Resources (2):**
- `accounting://accounts` — full COA (number, name, type, subtype) as standing context.
- `accounting://trial-balance` — current trial balance as JSON text.

**Prompts (3)** (surface as slash commands in Claude):
- `monthly_report` (arg `month: str`) — template: pull income statement + Cash ledger + budget report for the month, produce a plain-English monthly close summary.
- `tax_position` — template: pull ledgers for 2200 Taxes Payable + 2210 Tax Recoverable, compute net tax owed, explain in plain English.
- `cash_position` — template: pull Cash ledger + reconciliations, summarize cash on hand vs last statement.

**Transports & security:**
- `python mcp_server.py` → **stdio** (default). Targets: LM Studio (local Qwen), Claude Desktop/Code, ollmcp (Ollama), Qwen Code, opencode.
- `python mcp_server.py --http [--port 8765] [--host 127.0.0.1]` → **streamable HTTP**. Targets: ChatGPT remote connector, OpenAI Agents SDK, Anthropic Messages API. **Bearer token required**: env `MCP_HTTP_TOKEN`; if unset in HTTP mode, refuse to start with a clear message. Default bind `127.0.0.1` (UE ships loopback-with-no-auth; we're stricter — financial data).
- `python mcp_server.py --print-config <lmstudio|claude-code|claude-desktop|cursor|ollmcp|qwen-code|opencode>` → print the ready-to-paste client config (UE's `GenerateClientConfig` idea).
- No deprecated features: no roots/sampling/logging support anywhere.

**Testing (`tests/test_mcp_server.py`)** — SDK in-memory pattern:
- `from mcp import Client`; `async with Client(mcp) as client: result = await client.call_tool("list_accounts", {})`; assert on `result.structured_content`. Use `@pytest.mark.anyio` (add `anyio` to requirements if not already present via `mcp`).
- **DB setup**: reuse the `tests/conftest.py` pattern — set `ACCOUNTING_DB_PATH` to a temp file before importing app modules; then call `app/seed/demo.py::seed_demo_data()` for rich fixture data (it creates the demo user + full balanced business).
- Cover: every read tool returns expected structured content (spot-check values against seeded data); `search_transactions` finds a seeded entry by description text; dual money fields present (`*_cents` + formatted); unknown account → `isError` result (not an exception); **write tools absent by default**; with `MCP_ALLOW_WRITE=1` (monkeypatch env before `build_server()`): writes present, `create_journal_entry` posts a balanced entry (verify via `get_trial_balance`), unbalanced entry → error result, `create_invoice` for unknown customer → error result; resources listed + readable; prompts listed.
- Also unit-test the new `ledger.search_transactions` service function directly (filters, limit, account filter).

**Docs to update in the same phase:**
- **README.md**: new section "Using with an AI (MCP)" — brief research note (MCP standard, spec 2026-07-28, UE 5.8 experimental plugin as studied reference, curated-tools approach) + per-client setup snippets (LM Studio `mcp.json` for local Qwen; Ollama via `ollmcp`; Claude Desktop/Code `mcpServers`; ChatGPT/OpenAI/Anthropic remote connector) + env vars (`ACCOUNTING_DB_PATH`, `MCP_ALLOW_WRITE`, `MCP_HTTP_TOKEN`) + MCP Inspector debugging tip. Keep the AI-authorship framing.
- **AI_WORKFLOW.md**: add a Phase 12 entry (research → design → implementation).
- **AIHelper.md**: update via the maintain-aihelper skill at phase completion (roadmap status, conventions section, metadata).

**Implementation order (small steps, pytest green after each step):**
1. Add `mcp>=2` (+ `anyio` if missing) to `requirements.txt`; install via aliyun mirror; verify `import mcp` works.
2. `app/mcp/context.py` + `app/mcp/server.py` skeleton: `build_server()` registering ONE tool (`list_accounts`); `mcp_server.py` stdio entry; first in-memory client smoke test.
3. New `app/services/ledger.py::search_transactions` + direct service tests.
4. All 11 read tools in `app/mcp/tools.py` + per-tool in-memory tests.
5. 2 resources + 3 prompts + tests (listed + readable).
6. 7 write tools + `MCP_ALLOW_WRITE` gating + tests (absent by default, functional when enabled, error paths).
7. HTTP transport + `MCP_HTTP_TOKEN` enforcement + `--print-config` + manual smoke with MCP Inspector (`npx @modelcontextprotocol/inspector`).
8. README + AI_WORKFLOW.md + AIHelper updates; full `pytest` + `pyright app` green; commit + push (user's standing preference).

**Files to read first in a fresh session (before writing any code):**
- `AIHelper.md` — this section + "Established conventions" + "Environment & Tooling Notes"
- `app/database.py` — engine, `SessionLocal`, `init_db`, `ACCOUNTING_DB_PATH`
- `app/services/ledger.py` — `general_ledger`, `account_balance`, `trial_balance` signatures + return shapes
- `app/services/reports.py` — `income_statement`, `balance_sheet` signatures + return shapes
- `app/services/invoices.py`, `app/services/bills.py`, `app/services/estimates.py`, `app/services/budgets.py`, `app/services/reconciliation.py`, `app/services/accounts.py` — exact function signatures + return shapes (tools wrap these; verify names/params against code, not just this table)
- `app/services/export.py` — the `money(cents)` helper to reuse
- `app/services/errors.py` — `NotFoundError`/`ConflictError`/`ValidationError`
- `app/seed/demo.py` — what demo data looks like (useful for test expectations)
- `tests/conftest.py` — temp-DB env-var pattern
- SDK docs (web, if reachable): https://py.sdk.modelcontextprotocol.io/ — especially get-started, servers/tools, servers/structured-output, run/asgi, testing

## Architecture

Stack: Python 3.12 · FastAPI + uvicorn · SQLAlchemy 2.0 · SQLite (`accounting.db`) · vanilla HTML/CSS/JS SPA frontend (no build step, Phase 9) · ReportLab (PDF export) · pytest + TestClient.

```
Accounting/
├── main.py            # entry point: uvicorn runner (+ --seed flag)
├── mcp_server.py      # (Phase 12, pending) MCP entry point: stdio + streamable-HTTP
├── app/
│   ├── main.py        # FastAPI app factory, mounts, DB init, exception handlers
│   ├── database.py    # engine, session, schema init, COA seed hook
│   ├── dependencies.py# get_current_user (cookie session auth)
│   ├── models/        # Account, AccountType, User, JournalEntry, JournalLine, Customer, Vendor, Item, Invoice, Estimate, Bill, Budget, Reconciliation
│   ├── schemas/       # Pydantic v2 request/response models
│   ├── services/      # domain logic: accounts, auth, errors, journal, ledger, reports, parties, items, invoices, estimates, bills, budgets, reconciliation, export
│   ├── routers/       # auth, accounts, journal, ledger, reports, parties, items, invoices, bills, budgets, reconciliation, estimates, export
│   ├── mcp/           # (Phase 12, pending) context.py, tools.py, server.py — MCP tools/resources/prompts
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
| 20 | Phase 12 MCP: Python SDK **v2** (`MCPServer`, not legacy FastMCP); curated ~18 intent-oriented tools (11 read + 7 write) instead of API passthrough; tools separated from transport (UE 5.8 Toolset-Registry lesson); write tools gated behind `MCP_ALLOW_WRITE=1`; HTTP mode requires `MCP_HTTP_TOKEN` + loopback bind; dual money fields (cents + formatted USD) in every tool result; errors returned in tool results, not JSON-RPC errors; in-memory `Client(mcp)` for tests | Research (2026-09-25): spec 2026-07-28 is stateless (fits per-call sessions) and deprecates roots/sampling/logging; accounting prior art (Intuit 145-tool passthrough vs Xero/community 29-tool curated) favors curated tools for LLM reliability; UE 5.8's experimental Unreal MCP validates tool/transport separation and client-config generation; LM Studio hosts MCP natively for local Qwen, Ollama needs a bridge (ollmcp); financial data justifies stricter auth than UE's loopback-no-auth |

## Environment & Tooling Notes

- **venv**: `.venv` at project root (Python 3.12.10). Recreate with `py -3.12 -m venv .venv` then `.venv\Scripts\python.exe -m pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt`. Pinned via `.python-version` (`3.12`). Run everything with `.venv\Scripts\python.exe` (e.g. `.venv\Scripts\python.exe -m pytest`).
- **pip mirror**: `pypi.org` is unreachable from this machine (timeouts). Install with `-i https://mirrors.aliyun.com/pypi/simple/` (verified working).
- **LSP**: opencode's pyright LSP needs the venv — configured via `pyrightconfig.json` (`venvPath`/`venv`) and `opencode.jsonc` (`lsp.pyright.initialization.python.pythonPath`). If the LSP reports unresolved third-party imports (sqlalchemy, pytest, fastapi...), **restart opencode** so it reloads config; the code is fine if pytest passes.
- **Run app**: `.venv\Scripts\python.exe main.py` → http://127.0.0.1:8000 (OpenAPI docs at `/docs`). First API use requires `POST /api/auth/setup`.
- **Run tests**: `.venv\Scripts\python.exe -m pytest -v` (167 tests as of this update).
- **Type check**: `.venv\Scripts\python.exe -m pyright app` (pyright is installed in the venv and listed in `requirements.txt`; `pyrightconfig.json` pins it to `.venv`). Keep it at 0 errors.
- **DB file**: `accounting.db` (+ `-wal`/`-shm` sidecars) at project root, gitignored. Tests use a temp DB via `ACCOUNTING_DB_PATH`.
- **opencode.jsonc** is gitignored (local-only) and now contains the pyright venv config.

## Known Limitations

- No frontend unit tests yet (validated via `node --check` + a TestClient smoke script); a "wiring audit" test (every endpoint has an SPA caller) is a possible follow-up.
- No audit logging yet (planned pattern: SQLAlchemy `after_flush` hooks).

## AI Instructions

- **Phase 12 (MCP server) is the active work item** — fully researched and designed in the "Phase 12" section above; a fresh session should read that section plus the listed files, then implement in the given order. Phases 0–11 are Done.
- Any new work should follow the same "small steps, tests green after each step" rhythm and the conventions below.
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
- Last Incremental Update: 2026-09-25 (Phase 12 MCP: full web research — spec 2026-07-28 changelog, Python SDK v2 docs, UE 5.8 "Unreal MCP" experimental plugin docs, accounting MCP prior art (Intuit/Xero/AgenticBooks), local-model clients (LM Studio/Ollama) — plus complete approved design written into the "Phase 12" section (file layout, 11 read + 7 gated write tools, 2 resources, 3 prompts, transports/security, testing plan, implementation order, file reading list). README gained a "Using with an AI (MCP)" research section. Nothing implemented yet. Prior: Phase 11 seed + polish)
- Files Analyzed: web research (modelcontextprotocol.io spec 2026-07-28 + changelog, dev.epicgames.com UE 5.8 Unreal MCP docs, py.sdk.modelcontextprotocol.io, github.com/modelcontextprotocol/{python-sdk,servers}, LM Studio + Ollama MCP docs, accounting MCP servers), `app/database.py`, `README.md`, `AIHelper.md`
- Git Commit: `49a3c5c` (branch `main`, tracking `origin/main` at `git@github.com:Parsa-Mah/ai-accounting.git`; all phases 0–11 committed and pushed)
- Architecture Version: 0.12 (Phases 0–11 built; Phase 12 MCP designed, pending implementation)
- AIHelper Version: 3 (added Phase 12 research + design handoff section, decision 20)
