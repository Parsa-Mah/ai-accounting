# AIHelper — Accounting

## Project Summary

Python accounting web application (double-entry bookkeeping core + invoicing, AR/AP, budgets, CSV/PDF export). The project exists to demonstrate that a **local AI model writes the entire application** — the app is the vehicle, AI authorship is the product.

## Project Goals

1. Primary: a complete, working accounting app authored 100% by AI (no human-written code).
2. Secondary: a real, coherent accounting domain implementation (not a toy).
3. Public presentation: README + `AI_WORKFLOW.md` must make AI authorship explicit (model, runtime, hardware).

## Current Project Status (pre-implementation)

Only two files exist:

| File | State |
| --- | --- |
| `main.py` | Placeholder `print("Hello, World!")` — to be replaced by the app entry point |
| `README.md` | Final project front page (goal, stack, AI, hardware, author) |

No app code, no dependencies installed, no tests, no git repository yet.

## Authorship Rules (durable)

- All code in this repo is AI-generated; humans only direct and review.
- README states the author is **Parsa Mahmoodi** (programmer, coder, software engineer) and credits the AI.
- AI: **Qwen 3.8 27B** via **LM Studio** (llama.cpp backend) with **ROCm** on an **HP ZBook Ultra G1a** (AMD Ryzen AI MAX PRO 390, Radeon 8050S, 64 GB unified LPDDR5X).
- Never put secrets (serial numbers, device identifiers, keys) in repo files.

## Planned Architecture (approved, not yet implemented)

Stack: Python 3.13 · FastAPI + uvicorn · SQLAlchemy 2.0 · SQLite (`accounting.db`) · vanilla HTML/CSS/JS frontend (no build step) · ReportLab (PDF) · pytest + TestClient.

```
Accounting/
├── main.py            # entry point: uvicorn runner (+ --seed flag)
├── app/
│   ├── main.py        # FastAPI app factory, mounts, DB init
│   ├── database.py    # engine, session, schema init
│   ├── models/        # Account, JournalEntry, JournalLine, Invoice, Bill, Budget
│   ├── schemas/       # Pydantic v2 request/response models
│   ├── services/      # domain logic: validation, ledger, statements, posting, budgets
│   └── routers/       # accounts, journal, reports, invoices, bills, budgets, export
├── static/            # tabbed SPA: dashboard, accounts, journal, ledger, statements, invoices, bills, budgets, export
├── tests/
├── requirements.txt
├── .gitignore
├── README.md
└── AI_WORKFLOW.md     # to be written: how the AI built the project
```

Layering: `routers → services → models (SQLAlchemy) → SQLite`. Frontend calls REST `/api/*` endpoints via fetch.

### Domain invariants

- Every journal entry must balance: sum(debits) == sum(credits).
- Money is stored as **integer cents** end-to-end (no floats); convert to currency only at API/UI boundaries.
- Invoice posting auto-generates journal entries (Dr AR / Cr Revenue; payment: Dr Cash / Cr AR).
- Bill posting: Dr Expense / Cr AP; payment: Dr AP / Cr Cash.
- Balance sheet must satisfy Assets = Liabilities + Equity (incl. retained earnings).

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

## Known Limitations

- Nothing implemented yet; all architecture above is planned, not verified in code.
- No git history yet (repo not initialized); README's "see git history" claim becomes true only after `git init` + commits.

## AI Instructions

- Treat the planned architecture as the target design; verify against actual code once it exists — when code and this document disagree, update this document to match verified code.
- Keep the AI-authorship framing intact in any docs the AI writes.
- Do not start building the app without explicit user go-ahead.
- Run tests (`pytest`) and keep them green after changes once the test suite exists.

## Quick Project Facts

- Language/runtime: Python 3.13.15 (Windows, pwsh)
- Working dir: `D:\Projects\Python\GithubResume\Accounting`
- Parent dir `GithubResume` implies this is a GitHub portfolio project
- DB file (planned): `accounting.db` at project root

## Metadata

- Last Updated: 2026-09-21
- Last Full Scan: 2026-09-21
- Last Incremental Update: — (initial creation)
- Files Analyzed: `main.py`, `README.md` (full repo; only 2 files exist)
- Git Commit: n/a (not a git repository)
- Architecture Version: 0.1 (pre-implementation)
- AIHelper Version: 1
