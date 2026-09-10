#!/usr/bin/env python3
"""Measure control-plane overhead and budget correctness. Does not invent numbers."""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from psycopg import connect  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

from aicp.db import close_pool, configure_pool  # noqa: E402
from aicp.plane import FAKE, complete, restore_lab_runtime, seed_lab  # noqa: E402
from aicp.provider import FakeProvider, estimate_cost  # noqa: E402


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = min(len(s) - 1, max(0, int(round((p / 100) * (len(s) - 1)))))
    return s[k]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--eval-cases", type=int, default=100)
    args = parser.parse_args()

    dsn = os.environ.get("DATABASE_URL", "postgresql://workflow:workflow@127.0.0.1:5432/aicp")
    configure_pool(dsn)
    with connect(dsn, row_factory=dict_row) as conn:
        seed_lab(conn)
        restore_lab_runtime(conn)
        conn.execute(
            "UPDATE aicp_features SET budget_requests = 100000 WHERE name = %s",
            ("support_reply",),
        )
        conn.commit()

    FAKE.reset()
    FAKE.delay_ms = 5.0
    raw = FakeProvider()
    raw.delay_ms = 5.0

    raw_ms: list[float] = []
    for i in range(args.n):
        t0 = time.perf_counter()
        raw.complete("fake-small", "Be brief. JSON_ONLY", f"hello-{i}", 2000)
        raw_ms.append((time.perf_counter() - t0) * 1000)

    plane_ms: list[float] = []
    overhead: list[float] = []
    tenant = f"bench-{uuid4().hex[:8]}"
    t_all = time.perf_counter()
    for i in range(args.n):
        out = complete("support_reply", tenant, f"hello-{i}")
        if not out["ok"]:
            raise SystemExit(f"complete failed: {out}")
        plane_ms.append(out["latency_ms"])
        overhead.append(out["overhead_ms"])
    elapsed = time.perf_counter() - t_all
    tput = args.n / elapsed

    FAKE.reset()
    FAKE.delay_ms = 5.0
    with connect(dsn, row_factory=dict_row) as conn:
        restore_lab_runtime(conn)

    results = []
    with ThreadPoolExecutor(max_workers=32) as pool:
        futs = [pool.submit(complete, "paid_summarize", "bench-race", "hello") for _ in range(80)]
        for fut in as_completed(futs):
            results.append(fut.result())
    ok_n = sum(1 for r in results if r["ok"])

    from aicp.eval import check
    from aicp.provider import FakeProvider as FP

    fp = FP()
    t_eval = time.perf_counter()
    passed = 0
    for i in range(args.eval_cases):
        text = fp._render("Be brief. JSON_ONLY", f"hello-{i}")
        ok, _ = check("json_schema", {"required": ["ok"]}, text)
        passed += int(ok)
    eval_s = time.perf_counter() - t_eval

    with connect(dsn, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT coalesce(sum(tokens_in),0) AS tin,
                   coalesce(sum(tokens_out),0) AS tout,
                   coalesce(sum(cost_usd),0) AS cost
            FROM aicp_traces WHERE tenant = %s AND status = 'ok'
            """,
            (tenant,),
        ).fetchone()
    expected = estimate_cost("fake-small", int(row["tin"]), int(row["tout"]))
    drift = abs(float(row["cost"]) - expected)

    t_kill = time.perf_counter()
    from aicp.plane import set_killed

    with connect(dsn, row_factory=dict_row) as conn:
        set_killed(conn, "support_reply", True)
    killed = complete("support_reply", tenant, "after-kill")
    kill_ms = (time.perf_counter() - t_kill) * 1000

    report = {
        "ts": datetime.now(UTC).isoformat(),
        "host": platform.node(),
        "python": platform.python_version(),
        "n": args.n,
        "raw_provider_ms": {
            "p50": round(pct(raw_ms, 50), 3),
            "p99": round(pct(raw_ms, 99), 3),
            "mean": round(statistics.fmean(raw_ms), 3),
        },
        "complete_ms": {
            "p50": round(pct(plane_ms, 50), 3),
            "p99": round(pct(plane_ms, 99), 3),
            "mean": round(statistics.fmean(plane_ms), 3),
        },
        "overhead_ms": {
            "p50": round(pct(overhead, 50), 3),
            "p99": round(pct(overhead, 99), 3),
            "mean": round(statistics.fmean(overhead), 3),
        },
        "completes_per_s": round(tput, 2),
        "budget_race": {"attempts": 80, "cap": 10, "ok": ok_n},
        "eval_cases": args.eval_cases,
        "eval_seconds": round(eval_s, 4),
        "cost_drift_usd": round(drift, 8),
        "kill_switch_ms": round(kill_ms, 3),
        "kill_error_class": killed.get("error_class"),
        "note": (
            "Fake provider delay_ms=5. Overhead is complete() minus provider_ms. "
            "Not a production capacity rating. Real SDK latency would dominate."
        ),
    }
    out_path = ROOT / "bench-results.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    close_pool()


if __name__ == "__main__":
    main()
