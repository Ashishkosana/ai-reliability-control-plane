from __future__ import annotations

from aicp.plane import complete


def test_happy_path(client) -> None:
    out = complete("support_reply", "acme", "hello")
    assert out["ok"] is True
    assert out["trace_id"]
    assert "ok" in out["text"].lower() or "ok" in out["text"]
    traces = client.get("/traces?feature=support_reply").json()["traces"]
    assert traces
    row = traces[0]
    assert row["input_hash"]
    assert len(row["input_preview"]) <= 80
    assert row["prompt_version"] == 1


def test_unknown_feature() -> None:
    out = complete("nope", "acme", "x")
    assert out["ok"] is False
    assert out["error_class"] == "policy"


def test_kill_switch(client) -> None:
    client.post("/features/support_reply/kill")
    out = complete("support_reply", "acme", "hello")
    assert out["ok"] is False
    assert out["error_class"] == "kill_switch"
    client.post("/features/support_reply/unkill")
    out2 = complete("support_reply", "acme", "hello")
    assert out2["ok"] is True


def test_timeout_does_not_fallback() -> None:
    from aicp.plane import FAKE

    FAKE.mode = "slow"
    out = complete("support_reply", "acme", "hello", timeout_ms=20)
    assert out["ok"] is False
    assert out["error_class"] == "timeout"
    assert out.get("used_fallback") is False


def test_retry_then_ok() -> None:
    from aicp.plane import FAKE

    FAKE.mode = "fail_once"
    out = complete("support_reply", "acme", "hello")
    assert out["ok"] is True
    assert out["retried"] is True


def test_fallback_on_hard_fail() -> None:
    from aicp.plane import FAKE

    FAKE.mode = "fail"
    out = complete("support_reply", "acme", "hello")
    assert out["ok"] is True
    assert out["used_fallback"] is True
    assert out["model"] == "fake-fallback"
