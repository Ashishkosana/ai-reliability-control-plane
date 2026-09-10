from __future__ import annotations


def test_health(client) -> None:
    assert client.get("/health").json()["status"] == "ok"


def test_console_served(client) -> None:
    html = client.get("/").text
    assert "not a chat" in html.lower() or "not a chat window" in html
    assert "complete(feature" in html


def test_complete_endpoint(client) -> None:
    res = client.post(
        "/complete",
        json={"feature": "support_reply", "tenant": "api", "input": "hello"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    tid = body["trace_id"]
    got = client.get(f"/traces/{tid}")
    assert got.status_code == 200
    assert got.json()["input_hash"]


def test_eval_and_promote_http(client) -> None:
    blocked = client.post("/features/support_reply/eval", json={"version": 2}).json()
    assert blocked["blocked"] is True
    refused = client.post(
        "/features/support_reply/promote",
        json={"version": 2, "eval_run_id": blocked["id"]},
    )
    assert refused.status_code == 409
    good = client.post("/features/support_reply/eval", json={"version": 3}).json()
    assert good["blocked"] is False
    ok = client.post(
        "/features/support_reply/promote",
        json={"version": 3, "eval_run_id": good["id"]},
    )
    assert ok.status_code == 200
    assert ok.json()["active_version"] == 3


def test_kill_http(client) -> None:
    client.post("/features/support_reply/kill")
    body = client.post(
        "/complete",
        json={"feature": "support_reply", "tenant": "k", "input": "x"},
    ).json()
    assert body["error_class"] == "kill_switch"


def test_demo_provider_requires_demo(client) -> None:
    res = client.post("/demo/provider", json={"mode": "fail"})
    assert res.status_code == 200
    assert res.json()["mode"] == "fail"
