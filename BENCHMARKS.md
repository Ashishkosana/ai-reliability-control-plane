# Benchmarks

Numbers below were measured on this agent VM with the **fake** provider (`delay_ms=5`). They are not a capacity rating and they are not OpenAI latency.

Re-run:

```bash
export DATABASE_URL=postgresql://workflow:workflow@127.0.0.1:5432/aicp
python scripts/bench.py --n 200
```

Results are also written to `bench-results.json` (gitignored). These figures are from that file. They were not typed from memory.

## Host

| Field | Value |
| --- | --- |
| Host | `cursor` (this agent VM) |
| Python | 3.12.3 |
| Postgres | 16.15 |
| CPUs / RAM | 4 / 15 GiB |
| Provider | fake-small, `delay_ms=5` |

## Overhead vs raw fake SDK (n=200 serial `support_reply`)

| Metric | Raw provider | `complete()` | Overhead (`complete` − provider) |
| --- | --- | --- | --- |
| p50 | **5.15 ms** | **5.95 ms** | **0.86 ms** |
| p99 | **5.28 ms** | **6.96 ms** | **1.85 ms** |
| mean | 5.16 ms | 6.03 ms | 0.94 ms |

Throughput: **125.7 completes/s**. That is almost entirely the 5 ms fake sleep (200 × 5 ms ≈ 1.0 s plus SQL). It is not a claim about hosted LLMs.

What would force V2: overhead p99 that is large **relative to a real provider**. Against a 5 ms fake, 0.86–1.85 ms of SQL looks visible. Against a 400 ms model call it would not. Do not use this table to justify Redis.

## Budget correctness

80 concurrent calls, cap 10 on `paid_summarize`.

| Attempts | Cap | Completions |
| --- | --- | --- |
| 80 | 10 | **10** |

Slack of 0. The increment is not a suggestion.

## Eval runtime

100 `json_schema` checkers against the fake renderer: **0.0003 s**. If this were 1,000 slow LLM-judge calls, people would bypass the gate. That is why V1 does not use a judge as the gate.

## Kill switch

Time from `set_killed` to a failing `complete()`: **8.8 ms**. V1 has no config cache, so this is “a SQL read plus a denied call.” Error class: `kill_switch`.

## Cost accuracy

Sum of `aicp_traces.cost_usd` vs `estimate_cost(model, sum tokens_in, sum tokens_out)` for the bench tenant. Drift: **$0**. Fake prices are exact. Real vendor bills will not be; document reconciliation error when a real SDK exists.

## Interpretation

V1 holds for the laboratory. The fake provider is the right dependency until a drill needs a vendor error shape. No V2.
