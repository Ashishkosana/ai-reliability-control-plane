# Security notes

- No authentication on the HTTP adapter. Bind to localhost in any shared environment. `DEMO_MODE` injects provider faults; leave it `false` outside the lab.
- Default traces store a SHA-256 and an 80-character preview, not the raw prompt/input. Turn `store_payloads` on only for a debug tenant.
- Kill switch and budget are not authz for end users. They are operator controls. Do not confuse them with “the model cannot see this tenant’s data.”
- Request bodies are capped (`MAX_BODY_BYTES`).
- There is no real vendor API key in V1. `.env.example` has an empty `OPENAI_API_KEY` so nobody copies a secret into traces by accident.
- SQL is parameterized. Feature names in paths are not concatenated into queries without placeholders.
- The console is static HTML served by the API. It is not a place to paste production user content.
