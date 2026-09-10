# Failure drills

Automated in `drills/` and `tests/`. Walk them in the console with `DEMO_MODE=true`.

## 1. Kill switch

`POST /features/support_reply/kill` then `complete()`. Expect `error_class=kill_switch`, provider call count unchanged. Unkill restores traffic. In-flight calls that already passed the check finish; that is documented, not a bug.

## 2. Budget race

`paid_summarize` cap is 10. 100 concurrent `complete()` calls. Expect **exactly 10** `ok` and 90 `budget`. `aicp_budgets.request_count = 10`. If 11 succeed, the increment is wrong.

## 3. Provider timeout

Fake provider `mode=slow`, caller `timeout_ms=20`. Expect `timeout`, `used_fallback=false`. Budget request was reserved; tokens/USD stay 0 because nothing succeeded.

## 4. Retry then fallback, no storm

`mode=fail` on `support_reply` (has `fake-fallback`). The fake provider fails **primary** models only; `fake-fallback` still answers. Expect 3 provider calls: primary, retry, fallback. Not a loop.

## 5. Store down, fail closed

Pool closed / unreachable. `support_reply` returns `store_down` and does not increment provider calls.

## 6. Store down, fail open

Injected failure in `reserve_budget` for `lab_open`. Expect `ok=true`, `unmetered=true`, provider called, `aicp_unmetered_total` increments.

## 7. Weak eval vs strong eval (this one is supposed to hurt)

`support_reply` v2 body contains `LEAK_PREFIX`. Output looks like `NOTE: hello :: ok`.

- Checker `contains ok` → **pass**
- Checker `no_prefix NOTE:` → **fail**
- Checker `json_schema` → **fail**

Full eval blocks promote. Weak eval (`checkers=["contains"]`) would have shipped it. Live version remains v1. This is the lesson: eval coverage is the product.

## 8. Good promote

v3 (`JSON_ONLY REFUSE_SECRETS`) clears the golden set. `promote` moves the live pointer. `aicp_promote_events.accepted=true`.

## 9. Trace loss after success

`write_trace` raises. Caller still receives `ok=true` and the text. `aicp_trace_write_fail_total` increments.

## 10. Payload preview, not a warehouse

A long SSN-like input is hashed. Preview length ≤ 80 when `store_payloads=false`. Full raw input is not in `aicp_traces`.
