from __future__ import annotations

from aicp.plane import complete
from aicp.traces import configure, flush


def test_async_trace_still_lands(client) -> None:
    configure(True, maxsize=256)
    out = complete("support_reply", "async-tenant", "hello")
    assert out["ok"] is True
    flush()
    traces = client.get("/traces?tenant=async-tenant").json()["traces"]
    assert traces
    assert traces[0]["input_hash"]
    configure(False)
