# AI reliability control plane

A **synchronous policy layer** in front of model calls: tenant budgets, kill switch, immutable prompt versions, eval-gated promote, traces. Not a chatbot. Not a wrapper SDK demo.

**Stack:** Python 3.12 · FastAPI · PostgreSQL 16 · psycopg 3 · deterministic fake provider (laboratory)

**Problems this repo actually solves:** unmetered concurrent calls racing a cap; shipping a prompt because a weak checker said “ok”; a dead policy store that fails open and explodes the bill; traces that become a PII warehouse; a kill switch that nobody can explain.

**Why it is interesting:** the product is *control*, not model quality. We show a version that **looks** fine (`contains ok`) and is **blocked** by `no_prefix` / `json_schema`. The control plane does not claim the model is correct.

Callers use one function:

```text
complete(feature, tenant, input, timeout) → {ok, text, trace_id, …} | {ok: false, error_class, trace_id}
```

**Guarantee:** every accepted call is metered with `UPDATE … WHERE request_count < cap` and attributed to an immutable prompt version. Failed evals cannot promote. Availability of the *model* is out of scope.

This repository is **Project 2 only**. It is not the workflow engine and not the event platform.

## How a call is controlled

```mermaid
flowchart TD
  App["application complete(feature, tenant, input)"] --> Load[load feature row]
  Load -->|unknown| Policy[error policy]
  Load -->|killed| Kill[error kill_switch — no provider call]
  Load --> Budget["UPDATE budget WHERE request_count < cap RETURNING"]
  Budget -->|0 rows| Cap[error budget]
  Budget -->|store down and fail_closed| Down[error store_down]
  Budget -->|store down and lab_open| Open[unmetered=true, still call]
  Budget -->|reserved| Prompt[immutable active prompt version]
  Prompt --> Provider[fake provider]
  Provider -->|retryable| Retry[one retry]
  Retry -->|still failing, not timeout| Fallback[one fallback model]
  Provider --> Trace[trace: hash + 80-char preview]
  Trace --> Out[return result even if trace write drops]
```

Promote is a **separate** path. It is not on the hot path.

```mermaid
flowchart LR
  V[prompt version row — immutable] --> E[eval run — checkers]
  E -->|pass_rate < 0.8| Block[promote refused]
  E -->|pass_rate ≥ 0.8| Live[active_version_id moves]
```

There is no worker fleet. `complete()` runs in the calling process against Postgres. V2: traces enqueue to a bounded in-memory queue (`TRACE_ASYNC=true`); budget and kill switch stay synchronous. Tests set `TRACE_ASYNC=false`.

## What it is not

- A chat UI
- A RAG app
- An agent framework
- “We wrapped OpenAI for you”
- A semantic cache (explicitly out of V1; same text ≠ same tenant context)

The engineering console is a policy/trace inspector. If you need a conversation window, you are in the wrong repository.

## Hot path

1. Load feature config (active prompt version, model, timeout, fallback, kill switch, fail-closed).
2. If killed → error `kill_switch`, no provider call.
3. Reserve one request on `(tenant, feature, window)` atomically. If the cap is hit → error `budget`.
4. Call the fake provider. Retry **once** if the error is retryable. Otherwise try the fallback model unless the error is `timeout`.
5. Record USD spend. Persist a trace (hash + preview by default).
6. Return the result even if the trace write fails (`aicp_trace_write_fail_total`) or the async queue drops (`aicp_trace_queue_drop_total`).

If the control-plane store is down: **fail closed** by default. `lab_open` is the explicit fail-open feature for the drill.

## Lab features

| Feature | Role |
| --- | --- |
| `support_reply` | Prompt versions 1–3, fallback model, golden eval set |
| `paid_summarize` | Tight budget (10 requests / window) for the race drill |
| `lab_open` | `fail_closed=false` so a dead budget store still calls the provider and sets `unmetered=true` |

Prompt versions for `support_reply`:

| Version | Body flags | Full eval |
| --- | --- | --- |
| v1 | `JSON_ONLY` | 3/4 — live because it was seeded, not because it passed the gate |
| v2 | `LEAK_PREFIX` | **blocked** — `contains ok` still passes; `no_prefix` and `json_schema` catch the leak |
| v3 | `JSON_ONLY REFUSE_SECRETS` | 4/4 — the version you can promote |

That v2 row is the product. A weak checker would have shipped a leaked assistant prefix.

## 60-second demo

Complete a call → eval v2 (blocked) → eval v3 (promotable) → kill switch. Commands: [DEMO.md](DEMO.md).

## Run locally

Requires Python 3.12 and PostgreSQL 16. Use a **dedicated database** (`aicp`), not the workflow-engine database.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

docker compose up -d postgres   # if you have Docker

export DATABASE_URL=postgresql://workflow:workflow@127.0.0.1:5432/aicp
export DEMO_MODE=true
python -m aicp.api          # http://127.0.0.1:43190
```

Open `/` for the engineering console. CLI:

```bash
aicp complete support_reply --tenant acme --input hello
aicp eval support_reply 2
aicp promote support_reply 2 --eval-id <id>    # refused
aicp eval support_reply 3
aicp promote support_reply 3 --eval-id <id>    # accepted
aicp kill paid_summarize
aicp budget --tenant acme
aicp traces --feature support_reply
```

## Tests and CI

```bash
export TEST_DATABASE_URL=postgresql://workflow:workflow@127.0.0.1:5432/aicp_test
pytest -q
ruff check src tests drills scripts
ruff format --check src tests drills scripts
mypy src
```

GitHub Actions: `.github/workflows/ci.yml` (ruff, format, mypy, pytest) with Postgres 16.

## Error classes

`policy`, `kill_switch`, `budget`, `store_down`, `timeout`, `rate_limit`, `provider_5xx`.

## Docs

| File | What it is |
| --- | --- |
| [DEMO.md](DEMO.md) | Eval gate + kill switch in under a minute |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Why SQL budgets, fake provider, fail-closed |
| [DECISIONS.md](DECISIONS.md) | ADRs |
| [FAILURE_DRILLS.md](FAILURE_DRILLS.md) | Kill, race, timeout, weak eval |
| [BENCHMARKS.md](BENCHMARKS.md) | Overhead vs 5 ms fake; 80 concurrent vs cap 10 |
| [INTERVIEW_GUIDE.md](INTERVIEW_GUIDE.md) | How to defend this without sounding like a chatbot |
| [SECURITY.md](SECURITY.md) | No auth; hash+preview traces |
| [V2_PROPOSAL.md](V2_PROPOSAL.md) | Async trace append (implemented) |

## What V1/V2 do not do

No real vendor SDK on the hot path (fake provider is the laboratory; a real client is a swap). No semantic cache. No LLM-as-judge gate. No multi-agent anything. In-flight provider calls are not cancelled on kill. Benchmarks are **not** hosted-LLM latency.
