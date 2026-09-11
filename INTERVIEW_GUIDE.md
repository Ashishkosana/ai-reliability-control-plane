# Interview guide — AI reliability control plane

Defend *this* tree. If the answer sounds like LangSmith marketing, stop and open `plane.py`.

## 30-second explanation (recruiter)

Applications should not call a model SDK with a raw prompt string. I built a small control plane: one function, `complete(feature, tenant, input)`. Postgres holds tenant budgets, a kill switch, and immutable prompt versions. You cannot promote a version until a deterministic eval passes. It is not a chatbot. It does not claim the model is right — it claims we can meter, stop, and refuse to ship a prompt that fails property checks.

## 2-minute technical explanation

**Problem.** Direct SDK calls have no tenant cap, no kill switch, no prompt identity, and no trace you can reconstruct after a bad output ships. “Add Redis” does not fix a lost update on the budget row. “Add an LLM judge” makes the gate slow and circular.

**Architecture.** Synchronous `complete()` in `src/aicp/plane.py`. Load feature → kill check → `UPDATE aicp_budgets SET request_count = request_count + 1 WHERE request_count < cap RETURNING` → load immutable prompt body → fake provider (one retry, then one fallback unless timeout) → record spend → trace (hash + 80-char preview). Promote is a separate write that requires an eval run with `pass_rate >= 0.8`.

**Hardest challenge.** A prompt that *looks* fine. `support_reply` v2 injects `LEAK_PREFIX`. Checker `contains ok` passes. `no_prefix` and `json_schema` fail. Full eval blocks promote. That miss is the product.

**Solution.** Deterministic checkers only (`eval.py`). Weak eval exists on purpose so you can explain production incidents. Fail closed if the store is down (`lab_open` is the fail-open drill). Return the model result if the trace write fails. V2: bounded async trace queue; budget/kill stay sync.

**Evidence.** `FAILURE_DRILLS.md`, `tests/test_eval.py`, `tests/test_promote.py`, `tests/test_budget.py`. Bench: 80 concurrent vs cap 10 → **exactly 10** OK; complete overhead p50 **~0.86 ms** vs a 5 ms fake — not an LLM latency claim (`BENCHMARKS.md`).

## Architecture walkthrough

1. HTTP `POST /complete` or CLI `aicp complete` calls `complete()`.
2. `load_feature` — unknown feature → `policy`. `killed` → `kill_switch`, no provider.
3. `reserve_budget` — one logical reservation per call, including retry/fallback hops. Cap hit → `budget`.
4. Store exception + `fail_closed` → `store_down`. `lab_open` continues with `unmetered=true`.
5. Active `aicp_prompt_versions` row is immutable; shipping a prompt is moving `active_version_id`.
6. Fake provider interprets prompt flags (`JSON_ONLY`, `LEAK_PREFIX`, `REFUSE_SECRETS`), not “model personality.”
7. Retry once if retryable; fallback unless `timeout` (caller deadline already gone).
8. Spend recorded for the model that produced tokens. Trace via `_safe_trace` / async queue.
9. `POST /features/{name}/eval` runs checkers against a golden set. `promote` refuses if blocked or below threshold. Live pointer unchanged on reject (`aicp_promote_events`).

## Important concepts

**Four numbers, not “AI quality.”** Kill switch is availability. Budget is cost. Overhead vs provider time is latency. Eval pass rate is a *proxy* for properties (JSON, forbidden prefix), not truth.

**Lost update.** `read; if n < cap; write n+1` loses under concurrency. `UPDATE … WHERE n < cap RETURNING` does not, for this increment, at read committed.

**Fail closed vs fail open.** Same shape as authorization. Paid features fail closed. `lab_open` exists so you can explain the other choice.

**Prompt versions are config.** The app names a **feature**, not a string literal.

**Offline eval vs online traces.** Promote is the gate. Traces are the monitor. A dashboard that cannot block a pointer move is not a control plane.

**Retry amplification.** At most one retry and one fallback. Timeouts do not fallback. One budget reservation covers the logical call.

**PII.** Default `store_payloads=false`: SHA-256 + preview. The debug impulse is to store everything.

**No semantic cache in V1.** Same prompt text, different tenant. A hash cache is a V2 *candidate* only if traces show duplicates.

**In-flight kill.** Kill is read at the start of `complete()`. A call that already passed finishes. We do not cancel in-flight provider HTTP.

## Design decisions

[DECISIONS.md](DECISIONS.md): SQL budget not Redis; fail closed; deterministic eval not a judge; return result if trace fails; no chat UI; fake provider so overhead numbers are about the *plane*.

## Tradeoffs

| Choice | Alternative | Why here |
| --- | --- | --- |
| SQL increment | Redis `INCR` | Race is inspectable with `SELECT`; 80 vs 10 must be exact |
| Fake provider | Real OpenAI SDK | SDK would dominate latency and need a secret |
| Deterministic checkers | LLM-as-judge | Judge is slow, costly, circular; 100 `json_schema` checks were 0.0003 s |
| Sync complete() | Worker queue | Policy is a function call, not a step runner (that is Project 1) |
| Async traces (V2) | Sync INSERT | Caller result must not wait on telemetry; drops are metered |
| Fail closed | Fail open | Unmetered paid traffic is the incident |

Do not use the 0.86 ms overhead table to justify Redis against a 400 ms model.

## Failure scenarios

| Event | Behavior |
| --- | --- |
| Kill after check passed | In-flight finishes; next calls `kill_switch` |
| 80 callers, cap 10 | Exactly 10 `ok`, rest `budget` |
| Primary `fail`, fallback configured | Primary + retry + fallback (3 calls), not a loop |
| Timeout | `timeout`, `used_fallback=false`, tokens/USD 0 |
| Store down, fail closed | `store_down`, provider count unchanged |
| Store down, `lab_open` | `ok`, `unmetered=true` |
| Trace INSERT / queue full | Caller still gets text; metric increments |
| Weak `contains` eval on v2 | Pass — and that is the incident if you promoted on it |
| Strong eval on v2 | Block promote |
| Long secret in input | Hash stored; preview ≤ 80 chars when `store_payloads=false` |

## Limitations

- Fake provider only. Not GPT latency, not vendor bills (fake drift $0).
- No auth on HTTP.
- Eval is property checks, not “the answer is right.”
- Kill does not abort in-flight HTTP.
- No RAG, agents, or chat.
- Overhead benches use `delay_ms=5`.

## Interview questions (answers from this tree)

1. **Why isn’t this a chatbot?** The console inspects policy and traces. A chat window would demonstrate a wrapper. ADR 6.

2. **What does `complete()` guarantee?** Metering + prompt identity + traces. Not model correctness. README guarantee sentence.

3. **How is the budget race closed?** `reserve_budget` SQL `UPDATE … WHERE request_count < cap RETURNING`. Test: 80 vs 10 → 10.

4. **Redis INCR?** Faster maybe. V1 uses SQL so the drill is inspectable. Revisit only if overhead dominates a *real* provider — benches say it will not.

5. **Fail closed or open?** Default closed. `lab_open` is the drill (`unmetered=true`).

6. **What is v2 for?** `LEAK_PREFIX`. Weak `contains ok` passes; `no_prefix` / `json_schema` fail. Promote blocked. `FAILURE_DRILLS.md` §7.

7. **Why not LLM-as-judge?** Slow, expensive, circular. Eval runtime for 100 `json_schema` checks: 0.0003 s in `BENCHMARKS.md`.

8. **Retry policy?** One retry if retryable, then one fallback, never recurse. Timeouts do not fallback. One budget reservation.

9. **Does kill cancel the vendor HTTP?** No. Check is at the start of `complete()`.

10. **Trace write fails — do we fail the user?** No. `aicp_trace_write_fail_total`. Availability over telemetry consistency.

11. **What is in a default trace?** Input hash, 80-char preview, model, tokens, cost, error class. Not raw PII.

12. **How do you ship a prompt?** Insert immutable version, eval, promote if `pass_rate >= PROMOTE_THRESHOLD` (0.8). App keeps calling the feature name.

13. **Why a fake provider?** Deterministic flags; no secret; overhead is the plane. Real SDK is an interface swap.

14. **Is this the workflow engine?** No. Separate git remote. This is synchronous policy. Project 1 is durable steps.

15. **Async traces (V2)?** Bounded queue; drop metric; tests force `TRACE_ASYNC=false`. Kill/budget still sync.

16. **Semantic cache?** Not in V1. Correctness hazard across tenants. Candidate only with duplicate evidence in traces.

17. **Cost accuracy?** Sum of `aicp_traces.cost_usd` vs `estimate_cost` on the fake: drift $0. Real vendor bills will not be.

18. **Authz vs kill switch?** Kill/budget are operator controls, not “the model cannot see this tenant’s data.” `SECURITY.md`.

19. **What error classes exist?** `policy`, `kill_switch`, `budget`, `store_down`, `timeout`, `rate_limit`, `provider_5xx`.

20. **What would force a real SDK?** A drill that needs vendor error shapes, and a secret. Not a prettier console.
