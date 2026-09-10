from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

REGISTRY = CollectorRegistry()

COMPLETES = Counter(
    "aicp_completes_total",
    "complete() outcomes",
    ["feature", "status", "error_class"],
    registry=REGISTRY,
)
BUDGET_REJECT = Counter(
    "aicp_budget_reject_total",
    "Requests rejected for budget",
    ["feature"],
    registry=REGISTRY,
)
KILL = Counter("aicp_kill_switch_total", "Killed-feature calls", ["feature"], registry=REGISTRY)
TRACE_LOSS = Counter("aicp_trace_write_fail_total", "Trace persist failures", registry=REGISTRY)
TRACE_DROP = Counter("aicp_trace_queue_drop_total", "Async trace queue drops", registry=REGISTRY)
UNMETERED = Counter("aicp_unmetered_total", "Fail-open unmetered provider calls", registry=REGISTRY)
COMPLETE_MS = Histogram(
    "aicp_complete_ms",
    "end-to-end complete() latency",
    ["feature"],
    registry=REGISTRY,
    buckets=(1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000),
)
OVERHEAD_MS = Histogram(
    "aicp_overhead_ms",
    "control-plane overhead excluding provider",
    ["feature"],
    registry=REGISTRY,
    buckets=(0.2, 0.5, 1, 2, 5, 10, 25, 50, 100),
)
PROVIDER_MS = Histogram(
    "aicp_provider_ms",
    "provider time inside complete()",
    ["feature"],
    registry=REGISTRY,
    buckets=(1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 2500),
)


def render() -> bytes:
    return generate_latest(REGISTRY)
