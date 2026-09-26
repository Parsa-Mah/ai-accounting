# AI Workflow — How This Application Was Built

This document is the record of *how* the Accounting application in this repository was built: by a local, open-weight AI model writing every line of code, over a five-day build (2026-09-21 → 2026-09-25), with a human setting the goals and steering but writing no code.

The complete git history is the primary evidence — each commit is one step of the AI's build, in order.

## The division of labor

| Role | Who | What they did |
| --- | --- | --- |
| Goals & decisions | Human (Parsa Mahmoodi) | Defined the project's purpose and scope, made the key decisions (recorded in the `AIHelper.md` decision log), reviewed output, and steered direction |
| Everything else | AI (Qwen 3.8 27B, local via LM Studio) | Architecture, all backend code, all frontend code, all tests, all documentation, the build plan itself |

The AI worked through [opencode](https://opencode.ai), a terminal-based AI coding agent, which gave it a shell, file editing, and a language server (pyright) for real-time diagnostics. The model ran entirely on the machine described in the [README](README.md) — no cloud inference.

## The core mechanism: a persistent knowledge base

A local model has a finite context window (here, 133,120 tokens). A whole application does not fit in one context, and a long build spans many sessions. The workflow's central answer to this is **`AIHelper.md`** — a compact, AI-maintained knowledge base at the repository root.

The loop:

1. **Start of every task:** the AI reads `AIHelper.md` first. It contains the project summary, the architecture, the file inventory, the coding conventions, the domain invariants, the decision log, and the build roadmap.
2. **During the task:** the AI reads only the minimum source files needed (located by targeted search), implements the change, and follows the documented conventions exactly.
3. **End of the task:** tests and type checks must be green before the work is accepted.
4. **At phase boundaries:** the AI updates `AIHelper.md` to reflect the new state — what now exists, what changed, what remains.

This means each session starts with a dense, accurate picture of the project instead of a blank mind, and the conventions never drift: every new module is written to the same rules the earlier ones followed. Two small "skills" shipped in `skills/` (`use-aihelper`, `maintain-aihelper`) encode this loop as reusable instructions.

## The build rhythm: phases, small steps, green tests

The AI wrote a phased build plan (the roadmap in `AIHelper.md`) and worked through it as a work queue. The rules:

- **Small steps:** each step touches 1–2 files.
- **Tests after every step:** `pytest` must be green before the next step starts. The suite grew monotonically — a step is not done until its tests exist and pass.
- **Type safety:** `pyright` must report 0 errors.
- **One commit per completed step:** the commit message describes the step; the history is the build log.
- **Extend, don't fork:** new features reuse the existing architecture (one posting path, one error-mapping point, one API wrapper) rather than creating parallel systems.

## The build, phase by phase

| Phase | What was built | Commits |
| --- | --- | --- |
| 0 | Foundation: venv, SQLite layer (WAL tuning), FastAPI app factory, uvicorn runner, test scaffolding | `1771ef4`, `d9ce747` |
| 1 | Chart of accounts: model, service, router, tests, 26-account standard COA auto-seeded on startup | `5d9721b` |
| 2 | Single-user auth: first-run setup, pbkdf2 password hashing, itsdangerous signed cookie sessions, route protection | `e3da47d`, `a0e07c9` |
| 3 | **The core** — double-entry journal: entry + line models with a DB-level debit-XOR-credit CHECK constraint, a single posting path every financial event must use, void-as-reversing-entry, provenance columns | `b1a603b` |
| 4 | Ledger & statements: account balances, general ledger with running balance, trial balance, income statement, balance sheet (Assets = Liabilities + Equity by construction) | `384cfd2`, `f1754dc` |
| 5 | Parties, items, estimates, invoices: AR posting with flat tax, payments, voids, estimate → invoice conversion | `85824eb` |
| 6 | Bills (AP): per-line expense accounts, tax recoverable, payments, voids | `d01cd93` |
| 7 | Budgets: planned vs actual per account over custom date ranges, variance report | `2f85c58` |
| 8 | Bank reconciliation: cleared-line locking, classic difference rule, void guard, schema migration guard for pre-existing databases | `8551ad8` |
| 9 | Frontend: a vanilla JS SPA (no build step) — hash router with lazy page imports, auth gate, 12 pages, shared line editor, all money handled as integer cents | `2f63afc` |
| 10 | Export: 7 reports as CSV and PDF (ReportLab) downloads, wired into the SPA | `572a965` |
| 11 | Seed & polish: `--seed` demo data (a full, balanced, demo-ready business), this document, README finalization | this phase |
| 12 | MCP server: 19 curated tools (12 read, 7 write gated behind `MCP_ALLOW_WRITE`), 2 resources, 3 prompts, stdio + streamable-HTTP transports, bearer-token auth, `--print-config` client configs, in-memory client tests | this phase |

Before writing any code, the AI also did a research step: it searched GitHub for existing open-source Python accounting applications to use as a reference architecture (documented in `AIHelper.md`), found the closest match was source-licensed and therefore not reusable, and adopted its *patterns* — single posting path, DB-level balance guard, void-as-reversal — implemented from scratch.

Phase 12 got its own research pass first: the current MCP specification (2026-07-28), the official Python SDK v2 (verified against the actual installed wheel's source, not just the docs), Unreal Engine 5.8's experimental first-party "Unreal MCP" plugin (as a reference for keeping tool definitions decoupled from the transport and for generating ready-made client configs), and the accounting MCP ecosystem (Intuit's 145-tool QuickBooks passthrough vs. Xero's and community servers' ~29 curated tools — the consensus that curated, intent-oriented tools are more reliable for LLMs shaped the tool catalog).

## How the AI kept quality high without a human reviewer in the loop

- **The domain checks itself.** Double-entry bookkeeping has built-in invariants: every entry must balance, the trial balance must tie, and the balance sheet must satisfy A = L + E. Tests assert these invariants on real data, so an arithmetic or posting mistake cannot pass silently.
- **The database enforces rules.** The debit-XOR-credit CHECK constraint and non-negative money constraints make invalid states unrepresentable, not merely untested.
- **Money is integer cents end-to-end.** No floats anywhere in the domain; conversion to currency strings happens only at the API/UI boundary.
- **Two independent checkers.** `pytest` (198 tests) for behavior, `pyright` for types — both must be green after every step.
- **The frontend was validated by execution.** With no build step and no frontend test framework, each page was exercised through the real HTTP stack (TestClient smoke checks) and syntax-checked with `node --check`.

## What the human actually did

- Chose the project's purpose (demonstrate a local model building a real application) and its scope.
- Made the decisions in the `AIHelper.md` decision log (stack, currency, tax model, auth model, seed strategy, …).
- Reviewed the AI's output and redirected when needed.
- Set up the environment (LM Studio, model download, hardware) and pushed the commits to GitHub.

Nothing else. No function, no test, no page, and no paragraph of documentation was hand-written.

## Reproducing a session

```
1. opencode                          # start the agent in the repo
2. "continue the build"              # the AI reads AIHelper.md,
                                     # finds the first non-done phase,
                                     # and works through it
```

That is the entire interface. The roadmap in `AIHelper.md` is the work queue; the conventions in the same file are the style guide; the tests are the acceptance criteria.
