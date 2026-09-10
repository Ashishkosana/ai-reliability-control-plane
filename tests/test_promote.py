from __future__ import annotations

from aicp.db import get_pool
from aicp.plane import promote, run_eval


def test_v2_blocked_by_full_eval() -> None:
    with get_pool().connection() as conn:
        run = run_eval(conn, "support_reply", 2)
    assert run["blocked"] is True
    assert run["pass_rate"] < 0.8
    checkers = {d["checker"]: d["ok"] for d in run["details"]}
    assert checkers["contains"] is True
    assert checkers["no_prefix"] is False
    assert checkers["json_schema"] is False


def test_weak_eval_would_ship_v2() -> None:
    with get_pool().connection() as conn:
        run = run_eval(conn, "support_reply", 2, checkers=["contains"])
    assert run["blocked"] is False
    assert run["pass_rate"] == 1.0


def test_promote_v2_refused() -> None:
    with get_pool().connection() as conn:
        run = run_eval(conn, "support_reply", 2)
        try:
            promote(conn, "support_reply", 2, __import__("uuid").UUID(run["id"]))
            raise AssertionError("promote should refuse")
        except PermissionError as exc:
            assert str(exc) == "eval_failed"
        live = conn.execute(
            """
            SELECT p.version FROM aicp_features f
            JOIN aicp_prompt_versions p ON p.id = f.active_version_id
            WHERE f.name = 'support_reply'
            """
        ).fetchone()
        assert live["version"] == 1


def test_promote_v3_accepted() -> None:
    with get_pool().connection() as conn:
        run = run_eval(conn, "support_reply", 3)
        assert run["blocked"] is False
        out = promote(conn, "support_reply", 3, __import__("uuid").UUID(run["id"]))
        assert out["active_version"] == 3


def test_promote_requires_eval() -> None:
    with get_pool().connection() as conn:
        try:
            promote(conn, "support_reply", 3, None)
            raise AssertionError("expected eval_required")
        except PermissionError as exc:
            assert str(exc) == "eval_required"
