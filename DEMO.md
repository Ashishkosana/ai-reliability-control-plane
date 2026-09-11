# 60-second demo — AI reliability control plane

Goal: show **policy → budgeted call → weak eval would ship a leak → strong eval blocks promote → kill switch**. Fake provider only. Do not demo a chat window.

API up (`DEMO_MODE=true` is optional for the console; CLI works either way):

```bash
export DATABASE_URL=postgresql://workflow:workflow@127.0.0.1:5432/aicp
python -m aicp.api    # http://127.0.0.1:43190
```

## Script

```bash
# 1. A metered completion (feature support_reply, seeded live version)
aicp complete support_reply --tenant acme --input hello

# 2. The lesson: v2 has LEAK_PREFIX. Full eval must fail. Promote must refuse.
aicp eval support_reply 2
aicp promote support_reply 2 --eval-id <eval-id-from-previous>
# Expect: refused. Live pointer stays on v1.

# 3. v3 is promotable
aicp eval support_reply 3
aicp promote support_reply 3 --eval-id <eval-id>

# 4. Kill switch: no provider call
aicp kill support_reply
aicp complete support_reply --tenant acme --input hello
# Expect: error_class=kill_switch
aicp unkill support_reply
```

Budget race (do not eyeball this; the test is the demo):

```bash
pytest tests/test_budget.py drills/test_failure_drills.py -q
```

`paid_summarize` cap is 10. Concurrent callers must yield **exactly** 10 successes.

## Console

Open `/`. Use complete, eval, promote, kill. It is an engineering inspector, not a product chat UI.

## Recording a GIF (optional)

Record the four CLI steps above. The clip must show v2 promote **rejected** and kill returning `kill_switch`. Do not record a fake chat session. Do not type invented pass rates into the README; copy the CLI JSON you actually got.
