# Decisions

## ADR 1 — Separate git repository from the workflow engine

Project 1 is a step runner. Project 2 is a synchronous policy plane around model calls. Sharing a git history would invite shared tables, shared release cadence, and a confused interview story. Same Postgres *server* is allowed. Same database name is not the default.

## ADR 2 — SQL budget, not Redis

Concurrent 80 callers against a cap of 10 must yield **exactly** 10 successes. `UPDATE … WHERE request_count < cap RETURNING` is the whole algorithm. If it ever admits 11, the budget is a suggestion.

## ADR 3 — Fail closed by default

A dead control-plane store that fails open is how bills explode. `lab_open` exists so the fail-open path is tested, not so paid features use it.

## ADR 4 — Deterministic eval as the only V1 gate

LLM-as-judge is slow, expensive, and circular (the thing you are gating evaluates itself). V1 checkers: `exact`, `contains`, `json_schema`, `no_prefix`, `refuses_password`. The laboratory includes a **weak** checker on purpose: `contains ok` lets v2 (`LEAK_PREFIX`) pass. The strong set blocks promote. That miss is documented, not “fixed” with a judge.

## ADR 5 — Return the model result if the trace write fails

The user-facing completion already happened. Swallowing it to keep traces consistent would turn a metrics outage into an availability outage. Trace loss is `aicp_trace_write_fail_total`.

## ADR 6 — No chat UI

A chat window would demonstrate a wrapper. This repo demonstrates kill switches, budgets, and eval gates. The console is an ops surface.

## ADR 7 — Fake provider in V1

Overhead numbers against a fake 5 ms provider are honest about the *plane*. They are not a claim about GPT. A real SDK is a provider interface swap when a secret exists and a drill needs vendor error shapes.
