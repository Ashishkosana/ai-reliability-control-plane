from __future__ import annotations

from aicp.metrics import TRACE_LOSS, UNMETERED
from aicp.plane import FAKE, complete


def test_fail_closed_store_down_does_not_call_provider() -> None:
    from aicp import db

    db.close_pool()
    before = FAKE.calls
    out = complete("support_reply", "acme", "hello")
    assert out["error_class"] == "store_down"
    assert FAKE.calls == before


def test_fail_open_budget_store_calls_unmetered(client) -> None:
    before = FAKE.calls
    before_unmetered = UNMETERED._value.get()  # type: ignore[attr-defined]

    def boom(*_a, **_k):
        raise RuntimeError("injected budget store down")

    import aicp.plane as plane

    original = plane.reserve_budget
    plane.reserve_budget = boom  # type: ignore[method-assign]
    try:
        out = complete("lab_open", "acme", "hello")
    finally:
        plane.reserve_budget = original  # type: ignore[method-assign]
    assert out["ok"] is True
    assert out["unmetered"] is True
    assert FAKE.calls == before + 1
    assert UNMETERED._value.get() == before_unmetered + 1  # type: ignore[attr-defined]


def test_fail_closed_budget_store_skips_provider() -> None:
    before = FAKE.calls
    import aicp.plane as plane

    original = plane.reserve_budget

    def boom(*_a, **_k):
        raise RuntimeError("injected budget store down")

    plane.reserve_budget = boom  # type: ignore[method-assign]
    try:
        out = complete("support_reply", "acme", "hello")
    finally:
        plane.reserve_budget = original  # type: ignore[method-assign]
    assert out["ok"] is False
    assert out["error_class"] == "store_down"
    assert FAKE.calls == before


def test_trace_loss_still_returns_result() -> None:
    import aicp.plane as plane

    original = plane.write_trace

    def boom(*_a, **_k):
        raise RuntimeError("injected trace loss")

    before = TRACE_LOSS._value.get()  # type: ignore[attr-defined]
    plane.write_trace = boom  # type: ignore[method-assign]
    try:
        out = complete("support_reply", "acme", "hello")
    finally:
        plane.write_trace = original  # type: ignore[method-assign]
    assert out["ok"] is True
    assert out["text"]
    assert TRACE_LOSS._value.get() == before + 1  # type: ignore[attr-defined]


def test_fallback_does_not_loop() -> None:
    FAKE.mode = "fail"
    before = FAKE.calls
    out = complete("support_reply", "acme", "hello")
    # primary + retry + fallback = 3 calls. Not a recursive storm.
    assert FAKE.calls - before == 3
    assert out["used_fallback"] is True
    assert out["retried"] is True


def test_kill_is_immediate(client) -> None:
    client.post("/features/paid_summarize/kill")
    out = complete("paid_summarize", "acme", "x")
    assert out["error_class"] == "kill_switch"


def test_payload_default_is_preview_not_warehouse(client) -> None:
    secret = "ssn-123-45-6789 extra padding to see truncation " * 4
    complete("support_reply", "acme", secret)
    traces = client.get("/traces?tenant=acme").json()["traces"]
    row = traces[0]
    assert row["input_hash"]
    assert len(row["input_preview"]) <= 80
    assert secret not in (row["input_preview"] or "")
