# Accounting

A full-featured double-entry accounting web application — **written entirely by AI**, from architecture to code to tests.

## What is this project?

This repository contains an accounting application built in Python. The app implements a real double-entry bookkeeping core — chart of accounts, journal entries, ledgers, trial balance, income statement, and balance sheet — plus invoicing, accounts receivable/payable, budgets, and CSV/PDF report export, all exposed through a web interface.

But the application is not the main point. **The main point is that the entire application was written by an AI.** No human wrote a single line of code in this project. The AI planned the architecture, wrote the backend, the frontend, the tests, and the documentation.

## The goal

To demonstrate that a **local, open-weight AI model running on a single consumer workstation** can produce a complete, coherent, working software project — not a snippet, not a toy, but a real application with a database, a REST API, a web UI, automated tests, and documentation.

## Why was it created?

- To show what local LLMs are capable of for end-to-end software engineering.
- To prove that capable AI coding no longer requires cloud APIs — a 27B-parameter model on a laptop-class mobile workstation is enough to build a full application.
- As a public, verifiable example: the complete git history shows an AI authoring the project step by step.

## Tech stack

| Layer     | Technology                          |
| --------- | ----------------------------------- |
| Language  | Python 3.13                         |
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

The project is under active development. See the git history for the AI's step-by-step build process.
