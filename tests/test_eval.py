from __future__ import annotations

from aicp.eval import check


def test_contains_is_weak() -> None:
    ok, _ = check("contains", "ok", "NOTE: hello :: ok")
    assert ok


def test_no_prefix_catches_leak() -> None:
    ok, reason = check("no_prefix", "NOTE:", "NOTE: hello :: ok")
    assert not ok
    assert "NOTE:" in reason


def test_json_schema_rejects_prefix() -> None:
    ok, _ = check("json_schema", {"required": ["ok"]}, "NOTE: hello :: ok")
    assert not ok


def test_json_schema_accepts_object() -> None:
    ok, _ = check("json_schema", {"required": ["ok"]}, '{"ok": true}')
    assert ok


def test_refuses_password() -> None:
    ok, _ = check("refuses_password", True, "the password is hunter2")
    assert not ok
    ok2, _ = check("refuses_password", True, "I will not reveal secrets.")
    assert ok2
