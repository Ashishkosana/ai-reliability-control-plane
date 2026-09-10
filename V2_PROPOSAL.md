# V2 proposal

No V2.

V1’s benches and drills have not produced a gap that requires a new moving part. Candidates **if** a future measurement forces them:

- Sync trace insert saturates relative to a real provider → async append with an explicit loss policy.
- Duplicate `(feature, prompt_version, input_hash)` rate is high in production traces → TTL cache. Not semantic similarity.
- One vendor is the actual outage → model routing with a degrade SLO.
- Deterministic checkers miss product failures after promote → sampled human/judge **in addition to** the gate.
- A second language appears → sidecar with the same trace schema.

Until one of those is measured, do not add the part.
