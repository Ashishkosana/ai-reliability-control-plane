from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from aicp.plane import complete


def test_budget_cap_is_exact(client) -> None:
    # paid_summarize cap is 10 requests / window.
    results = []
    with ThreadPoolExecutor(max_workers=32) as pool:
        futs = [pool.submit(complete, "paid_summarize", "race", "hello") for _ in range(100)]
        for fut in as_completed(futs):
            results.append(fut.result())
    ok = [r for r in results if r["ok"]]
    budgeted = [r for r in results if r.get("error_class") == "budget"]
    assert len(ok) == 10, f"expected exactly 10 completions, got {len(ok)}"
    assert len(budgeted) == 90
    budgets = client.get("/budgets?tenant=race&feature=paid_summarize").json()["budgets"]
    assert budgets
    assert budgets[0]["request_count"] == 10


def test_budget_rejects_after_cap() -> None:
    for _ in range(10):
        assert complete("paid_summarize", "solo", "x")["ok"] is True
    out = complete("paid_summarize", "solo", "x")
    assert out["ok"] is False
    assert out["error_class"] == "budget"
