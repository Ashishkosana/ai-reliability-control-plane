# Architecture

```text
application  →  complete()  →  Postgres (features, budgets, traces)
                     │
                     ├─ fake provider (V1 lab)
                     └─ HTTP adapter (FastAPI) for the console and CLI
```

The API process does not hide a worker fleet. `complete()` is synchronous. Kill switch, budget, and prompt version are checked in the calling process against Postgres.

## Why Postgres, not Redis

The interesting bug is a lost update on the budget row under concurrency. Redis `INCR` would likely be faster. V1 uses SQL so the race drill is inspectable with `SELECT`. Revisit if the overhead bench shows the row update dominating a real provider’s latency — it will not, until the provider is fake and 5 ms.

## Why a fake provider

A real SDK would dominate every latency histogram and require a secret. The control plane’s job is policy, accounting, and traces. The fake provider is deterministic: `LEAK_PREFIX`, `JSON_ONLY`, `REFUSE_SECRETS` are prompt flags, not model personality.

## Trace retention

Default `store_payloads=false`: SHA-256 of the input plus an 80-character preview. The control plane must not become a PII warehouse because someone wanted a pretty replay UI.

## Eval gate

`promote` requires an eval run id for that feature and version. If `pass_rate < PROMOTE_THRESHOLD` (0.8), the write is refused and a `aicp_promote_events` row records the rejection. Live pointer stays on the previous version.

## Fallback

One retry on retryable errors, then at most one fallback model. Timeouts do not fallback: the caller deadline is already gone. Request budget is reserved once for the logical call, not once per hop. USD spend follows the model that actually produced tokens.

## In-flight kill

The kill switch is read at the start of `complete()`. A call that already passed that check finishes. New calls fail fast. That is the V1 contract, not “cancel the in-flight HTTP request to the vendor.”
