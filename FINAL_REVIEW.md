# Final review (V1)

## What is true

- `complete()` is the only hot path.
- Budgets are atomic; the race drill expects exactly the cap.
- Kill switch is a feature row, checked at the start of `complete()`.
- Prompt versions are immutable. Promote requires an eval run that is not blocked.
- v2 (`LEAK_PREFIX`) is blocked by the strong golden set and would pass a `contains`-only set.
- Traces default to hash + preview. Trace write failure does not drop the caller result.
- Fail closed is default; `lab_open` is the fail-open drill.
- Fake provider only. Numbers in `BENCHMARKS.md` say so.

## What is not true

- Exactly-once anything.
- The model is “safe” because eval passed.
- Overhead numbers generalize to a hosted LLM.
- In-flight vendor HTTP is cancelled on kill.
- This repository includes the workflow engine.

- Async traces: bounded queue (`TRACE_ASYNC=true` default; tests force false).

## Open gaps that are not further V2 yet

- Real SDK error classification (need a vendor, or recorded fixtures).
- Authn on the HTTP adapter.

V2 async trace append is implemented. See [V2_PROPOSAL.md](V2_PROPOSAL.md). The laboratory still holds for the drills we ran.
