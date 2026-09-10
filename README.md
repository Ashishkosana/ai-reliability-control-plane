# AI reliability control plane

Applications should not call a model provider SDK directly. Direct calls have no tenant budget, no kill switch, no prompt version, and no trace you can reconstruct after a bad output ships.

This repository is **Project 2 only**. It is not the workflow engine. It is not a chatbot.

Callers use one function:

```text
complete(feature, tenant, input, timeout) → {ok, text, trace_id, …} | {ok: false, error_class, trace_id}
```

**Guarantee:** every accepted call is metered against a SQL budget (`UPDATE … WHERE request_count < cap`) and attributed to an immutable prompt version. Failed evals cannot promote. The control plane does **not** claim to make the model correct.

## What it is not

- A chat UI
- A RAG app
- An agent framework
- “We wrapped OpenAI for you”

The engineering console is a policy/trace inspector. If you need a conversation window, you are in the wrong repository.

## Hot path

1. Load feature config (active prompt version, model, timeout, fallback, kill switch, fail-closed).
2. If killed → error `kill_switch`, no provider call.
3. Reserve one request on `(tenant, feature, window)` atomically. If the cap is hit → error `budget`.
4. Call the fake provider (V1 laboratory). Retry **once** if the error is retryable. Otherwise try the fallback model unless the error is `timeout`.
5. Record USD spend. Persist a trace (hash + preview by default, not full PII).
6. Return the result even if the trace write fails (`aicp_trace_write_fail_total`).

If the control-plane store is down: **fail closed** by default (no unmetered provider call). `lab_open` is the explicit fail-open feature for the drill.

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

## Repository

This remote is **Project 2 only**. Project 1 (workflow engine) and Project 3 (`realtime-event-platform`) are different git remotes. Do not merge those codebases into this history.

Create an Origin or GitHub repository named `ai-reliability-control-plane`, then:

```bash
git remote add origin <that-repo-url>
git push -u origin main
```

## Run locally

Requires Python 3.12 and PostgreSQL 16. Use a **dedicated database** (`aicp`), not the workflow-engine database.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

# Docker, if you have it:
docker compose up -d postgres

# Or local Postgres:
#   createdb aicp   (user workflow / workflow in this lab)

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

Tests (real Postgres):

```bash
export TEST_DATABASE_URL=postgresql://workflow:workflow@127.0.0.1:5432/aicp_test
pytest -q
```

## Error classes

`policy`, `kill_switch`, `budget`, `store_down`, `timeout`, `rate_limit`, `provider_5xx`.

## What V1 does not do

No real vendor SDK on the hot path (the fake provider is the laboratory; a real client is a swap). No semantic cache. No LLM-as-judge gate. No multi-agent anything. See [V2_PROPOSAL.md](V2_PROPOSAL.md) — empty until a measured gap appears.
