# Accounting

A full-featured double-entry accounting web application — **written entirely by AI**, from architecture to code to tests.

## What is this project?

This repository contains an accounting application built in Python. The app implements a real double-entry bookkeeping core — chart of accounts, journal entries, ledgers, trial balance, income statement, and balance sheet — plus invoicing, accounts receivable/payable, budgets, and CSV/PDF report export, all exposed through a web interface.

But the application is not the main point. **The main point is that the entire application was written by an AI.** No human wrote a single line of code in this project. The AI planned the architecture, wrote the backend, the frontend, the tests, and the documentation. [AI_WORKFLOW.md](AI_WORKFLOW.md) is the full record of how the AI built it, phase by phase.

## The goal

To demonstrate that a **local, open-weight AI model running on a single consumer workstation** can produce a complete, coherent, working software project — not a snippet, not a toy, but a real application with a database, a REST API, a web UI, automated tests, and documentation.

## Why was it created?

- To show what local LLMs are capable of for end-to-end software engineering.
- To prove that capable AI coding no longer requires cloud APIs — a 27B-parameter model on a laptop-class mobile workstation is enough to build a full application.
- As a public, verifiable example: the complete git history shows an AI authoring the project step by step.

## Tech stack

| Layer     | Technology                          |
| --------- | ----------------------------------- |
| Language  | Python 3.12                         |
| Backend   | FastAPI + uvicorn                   |
| ORM       | SQLAlchemy 2.0                      |
| Database  | SQLite (file-based, ACID)           |
| Frontend  | Vanilla HTML / CSS / JavaScript     |
| PDF export| ReportLab                           |
| Tests     | pytest + FastAPI TestClient         |

## The AI

This project was authored by:

- **Model:** Qwen 3.8 27B
- **Runtime:** [LM Studio](https://lmstudio.ai) with the llama.cpp inference backend
- **GPU acceleration:** ROCm (AMD)
- **Code intelligence:** LSP (Language Server Protocol) enabled in the AI's editor for real-time diagnostics and symbol navigation

Everything ran locally — no cloud inference, no external API calls.

## Details and configurations of Qwen AI

### Model

| | |
| --- | --- |
| Model | Qwen 3.8 27B (27 billion parameters) |
| Quantized file | `Qwen3.8-27B-UD-Q5_K_XL.gguf` (Unsloth Dynamic Q5_K_XL) |
| Source | [unsloth/Qwen3.8-27B-GGUF](https://huggingface.co/unsloth) |
| Base model | [Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B) |
| License | Apache 2.0 |
| Native context window | up to 262,144 tokens |

Qwen describes the model as a "Renewal of the beloved Qwen model, delivering unmatched intelligence density."

### Inference configuration (LM Studio)

| Setting | Value | What it means |
| --- | --- | --- |
| Reasoning | On, unlimited budget | The model is allowed to think as long as it needs before answering |
| Context length | 133,120 tokens | How much of the conversation the model can see at once (about half of the model's native maximum) |
| Temperature | 0.6 | Slightly conservative sampling — favors accurate, consistent output over wild creativity |
| Top-k | 20 | Only the 20 most likely next tokens are considered at each step |
| Top-p | 0.95 | Tokens are drawn from the smallest set of candidates covering 95% of the probability |
| Min-p | Disabled | No additional probability floor filtering |
| Repeat penalty | Off | No artificial penalty for repeating content |
| Presence penalty | Off | No bonus for introducing new topics |
| Multi-token prediction (MTP) | On, up to 3 draft tokens | The model drafts a few tokens ahead and verifies them, speeding up generation |
| GPU offload | 65 / 65 layers | The entire model runs on the GPU (Radeon 8050S) |
| CPU thread pool | 12 threads | Matches the CPU's 12 cores |
| Evaluation batch size | 512 | Larger batches make prompt processing more efficient |
| Flash attention | On | Faster attention computation with lower memory usage |
| KV cache quantization | Q8_0 (both K and V) | Compresses the context cache so more context fits in memory, with minimal quality loss |
| Keep model in memory | On | The model stays loaded in RAM between generations |
| Memory-mapped loading (mmap) | Off | Deliberately disabled — a unified-memory leak bug (in llama.cpp, LM Studio, or ROCm) caused double memory usage across both VRAM and RAM when mmap was enabled |

Everything else is left at LM Studio defaults.

## Hardware

The AI ran on a single machine:

- **Device:** HP ZBook Ultra G1a 14" Mobile Workstation
- **CPU/GPU:** AMD Ryzen AI MAX PRO 390 with Radeon 8050S graphics (3.20 GHz)
- **Memory:** 64 GB unified LPDDR5X RAM

The unified memory architecture lets the GPU address the full 64 GB pool, which is what makes running a 27B-parameter model locally on a mobile workstation practical.

## Author

**Parsa Mahmoodi** — programmer, coder, and software engineer.

Parsa set the goals, reviewed the output, and steered the project. All code was generated by the AI described above.

## Status

The application is complete. All 13 build phases (0–12) are implemented and tested — 198 tests, all passing, with the type checker reporting zero errors. The full step-by-step build is visible in the git history, and [AI_WORKFLOW.md](AI_WORKFLOW.md) explains the process.

## Using with an AI (MCP)

The app ships an [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server, so **any AI assistant** — ChatGPT, Claude, or a local Qwen in LM Studio — can drive it like an accountant. Ask in plain English — *"What was March's payroll?"*, *"How much tax do we owe?"*, *"Which invoices are overdue?"* — and the AI calls typed tools and answers with real numbers from the books, or (opt-in) records a transaction on your behalf.

The server exposes **19 curated, intent-oriented tools** — deliberately not a raw API passthrough, because research on accounting MCP servers (Intuit's 145-tool QuickBooks server vs. Xero's and community servers' ~29 curated tools) shows curated tools are far more reliable for LLMs:

- **12 read tools, always on**: chart of accounts, income statement, balance sheet, trial balance, per-account ledger, free-text transaction search, invoices, bills, estimates, budget report, bank reconciliations.
- **7 write tools, opt-in** (set `MCP_ALLOW_WRITE=1`): journal entries, invoices, invoice payments, invoice voids, bills, bill payments, budgets. Every write goes through the same single posting path as the web app, so the books balance by construction.
- **2 resources**: the chart of accounts and the current trial balance, available to the model as standing context.
- **3 prompts** (slash commands in clients like Claude): `/monthly_report`, `/tax_position`, `/cash_position`.

Every tool result carries both integer cents and a formatted USD string, so even small local models can quote exact numbers. Errors come back as readable tool errors (e.g. *"Account 'Payroll' not found. Valid accounts: ..."*) that the model can recover from, not crashes.

### Running the MCP server

```bash
python mcp_server.py            # stdio transport (default) — for local clients
MCP_HTTP_TOKEN=your-secret python mcp_server.py --http   # streamable HTTP — for remote clients
```

HTTP mode binds `127.0.0.1:8765` (`--host` / `--port` to change) and refuses to start without the `MCP_HTTP_TOKEN` bearer token — financial data gets stricter auth than the loopback-no-auth default some other MCP servers ship.

| Variable | Meaning |
| --- | --- |
| `ACCOUNTING_DB_PATH` | SQLite file to open (default: `accounting.db` at the project root — the same file the web app uses; WAL mode makes concurrent access safe) |
| `MCP_ALLOW_WRITE` | Set to `1` to register the 7 write tools (default: read-only) |
| `MCP_HTTP_TOKEN` | Bearer token required for `--http` mode |

### Connecting a client

`python mcp_server.py --print-config <client>` prints a ready-to-paste config for `lmstudio`, `claude-code`, `claude-desktop`, `cursor`, `ollmcp`, `qwen-code`, or `opencode` (add `--http` for the remote URL + bearer-header variant):

- **LM Studio** (local Qwen): paste the `mcpServers` entry into LM Studio's MCP settings — a local Qwen can then ask the books questions directly.
- **Claude Desktop / Claude Code / Cursor / Qwen Code**: paste the `mcpServers` entry into the client's MCP config file.
- **Ollama**: Ollama is a model server, not an MCP client — use the bridge command it prints (`ollmcp mcp add accounting -- ...`), or point Cline / opencode at Ollama as the model backend.
- **ChatGPT / OpenAI Agents SDK / Anthropic Messages API**: run `--http` and point the remote connector at `http://127.0.0.1:8765/mcp` with the bearer token.
- **Debugging**: the standard debugging client is [MCP Inspector](https://github.com/modelcontextprotocol/inspector) (`npx @modelcontextprotocol/inspector`), or `mcp dev mcp_server.py` with the SDK's CLI extra.

The design rationale — curated tools vs. API passthrough, write gating, token auth, the tool catalog — is documented in [AIHelper.md](AIHelper.md) (section "Phase 12").

## Features

- **Double-entry core** — chart of accounts, journal entries, general ledger, trial balance
- **Financial statements** — income statement and balance sheet (Assets = Liabilities + Equity by construction)
- **Invoicing & AR** — flat tax, payments, partial payments, voids
- **Estimates** — quotes that convert to invoices in one step
- **Bills & AP** — per-line expense accounts, tax recoverable, payments, voids
- **Budgets** — planned vs. actual with variance, over custom date ranges
- **Bank reconciliation** — cleared-line locking and the classic difference rule
- **Export** — 7 reports as CSV and PDF
- **Auth** — single-user, first-run setup, signed cookie sessions
- **Web UI** — a vanilla JS SPA with no build step
- **Demo data** — a complete, balanced sample business via `--seed`
- **MCP server** — any AI assistant can query the books (and optionally record transactions) through 19 curated tools, over stdio or streamable HTTP

## Running the app

```bash
pip install -r requirements.txt
python main.py --seed   # optional: seed demo data first
```

Then open <http://127.0.0.1:8000>. With `--seed`, log in as `demo` / `demo123`; without it, the first visit shows a setup screen to create the account.

## Running the tests

```bash
pytest
```
