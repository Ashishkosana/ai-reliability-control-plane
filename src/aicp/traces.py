"""Best-effort async trace append. Drop is a metric, not a user-visible error."""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any

from aicp.metrics import TRACE_DROP, TRACE_LOSS

logger = logging.getLogger("aicp.traces")

_q: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=4096)
_thread: threading.Thread | None = None
_stop = threading.Event()
_enabled = False


def configure(enabled: bool, maxsize: int = 4096) -> None:
    global _q, _thread, _enabled
    _enabled = enabled
    _stop.clear()
    if _thread is not None and _thread.is_alive():
        return
    _q = queue.Queue(maxsize=maxsize)
    if not enabled:
        return
    _thread = threading.Thread(target=_loop, name="aicp-traces", daemon=True)
    _thread.start()


def enqueue(row: dict[str, Any]) -> None:
    if not _enabled:
        _write(row)
        return
    try:
        _q.put_nowait(row)
    except queue.Full:
        TRACE_DROP.inc()
        logger.warning("trace queue full; dropping")


def flush(timeout: float = 2.0) -> None:
    if not _enabled:
        return
    deadline_wait = timeout
    _q.join()
    # join waits forever if empty; Queue.join is fine when unfinished_tasks==0
    del deadline_wait


def _write(row: dict[str, Any]) -> None:
    try:
        from aicp.db import get_pool
        from aicp.plane import write_trace

        with get_pool().connection() as conn:
            write_trace(conn, row)
    except Exception:
        TRACE_LOSS.inc()
        logger.exception("async trace write failed")


def _loop() -> None:
    while not _stop.is_set():
        try:
            row = _q.get(timeout=0.2)
        except queue.Empty:
            continue
        try:
            _write(row)
        finally:
            _q.task_done()


def stop() -> None:
    _stop.set()
