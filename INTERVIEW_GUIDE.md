# Interview guide

Teach from this repo, not from a blog post.

## Four SLOs, not one “AI quality”

Availability, latency, cost, and quality are different numbers. A kill switch is availability. A budget is cost. p99 overhead vs provider time is latency. Eval pass rate is a **proxy** for quality, not quality.

## Why “accuracy” is usually undefined

There is no labeled distribution on the hot path. V1 gates on properties: JSON shape, forbidden prefix, refusal. That is weaker than “the answer is right” and stronger than “the model returned 200.”

## Offline eval vs online monitoring

`promote` is the gate. Traces are the monitor. A dashboard of pass rates that cannot block a pointer move is not a control plane.

## Fail open vs fail closed

Same shape as authorization: if the policy store is down, do you fail the request or skip the check? Paid features fail closed. The drill for `lab_open` exists so you can explain the other choice.

## Budget as a lost-update problem

`read count; if count < cap; write count+1` loses updates. `UPDATE … WHERE count < cap RETURNING` does not, under `read committed`, for this increment. Know the isolation level you are assuming.

## Retry amplification

Retry once, then fallback once, never recurse. Timeouts do not fallback. One budget reservation covers the logical call.

## Prompt versions are config

The application names a **feature**, not a prompt string. Shipping a prompt is pointing `active_version_id` at an immutable row after an eval.

## Semantic cache is a correctness hazard

Same prompt text, different tenant context. V1 does not cache completions. A hash cache keyed by `(feature, prompt_version, input_hash)` is a V2 **candidate** only if traces show duplicates.

## PII in traces

Hash + preview is the default because the debug impulse is to store everything. Be able to point at `store_payloads` and the drill that a long secret is not in the row.

## Whiteboard comparison

Not LangSmith, not Helicone, not “an LLM gateway product.” Those are fine products. This laboratory exists so you can defend *why* a budget is a SQL increment and *why* a weak `contains` checker is a production incident.
