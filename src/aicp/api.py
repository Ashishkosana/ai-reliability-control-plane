from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import UUID

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from aicp.config import Settings, load_settings
from aicp.db import close_pool, configure_pool, get_pool
from aicp.logging import setup_logging
from aicp.metrics import render as render_metrics
from aicp.plane import (
    FAKE,
    complete,
    create_prompt_version,
    jsonable,
    load_feature,
    promote,
    restore_lab_runtime,
    run_eval,
    seed_lab,
    set_killed,
)

logger = logging.getLogger("aicp.api")
settings: Settings = load_settings()


class CompleteBody(BaseModel):
    feature: str = Field(min_length=1, max_length=100)
    tenant: str = Field(min_length=1, max_length=100)
    input: str = Field(min_length=0, max_length=20_000)
    timeout_ms: int | None = Field(default=None, ge=1, le=60_000)


class PromptBody(BaseModel):
    body: str = Field(min_length=1, max_length=20_000)


class EvalBody(BaseModel):
    version: int = Field(ge=1)
    checkers: list[str] | None = None


class PromoteBody(BaseModel):
    version: int = Field(ge=1)
    eval_run_id: UUID


class ProviderBody(BaseModel):
    mode: str = Field(min_length=1, max_length=40)
    delay_ms: float | None = None


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"code": code, "message": message})


@asynccontextmanager
async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
    global settings
    settings = load_settings()
    setup_logging(settings.log_level)
    configure_pool(settings.database_url)
    from aicp.traces import configure as configure_traces

    configure_traces(settings.trace_async, settings.trace_queue_size)
    with get_pool().connection() as conn:
        seed_lab(conn)
    yield
    close_pool()


app = FastAPI(title="ai-reliability-control-plane", lifespan=lifespan)


@app.middleware("http")
async def limit_body(request: Request, call_next):  # type: ignore[no-untyped-def]
    length = request.headers.get("content-length")
    if length:
        if int(length) > settings.max_body_bytes:
            return _error(413, "payload_too_large", "request body exceeds MAX_BODY_BYTES")
        return await call_next(request)
    body = await request.body()
    if len(body) > settings.max_body_bytes:
        return _error(413, "payload_too_large", "request body exceeds MAX_BODY_BYTES")

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(request.scope, receive)
    return await call_next(request)


@app.get("/health")
def health() -> dict[str, str]:
    with get_pool().connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=render_metrics(), media_type="text/plain; version=0.0.4")


@app.post("/complete")
def do_complete(body: CompleteBody) -> dict[str, Any]:
    return complete(body.feature, body.tenant, body.input, body.timeout_ms)


@app.get("/features")
def features() -> dict[str, Any]:
    with get_pool().connection() as conn:
        rows = conn.execute(
            """
            SELECT f.*, p.version AS active_version, p.body AS active_body
            FROM aicp_features f
            LEFT JOIN aicp_prompt_versions p ON p.id = f.active_version_id
            ORDER BY f.name
            """
        ).fetchall()
    return {"features": jsonable([dict(r) for r in rows])}


@app.get("/features/{name}")
def feature_detail(name: str) -> Any:
    with get_pool().connection() as conn:
        feat = load_feature(conn, name)
        if feat is None:
            return _error(404, "unknown_feature", f"unknown feature {name}")
        prompts = conn.execute(
            """
            SELECT id, feature, version, left(body, 200) AS body, created_at
            FROM aicp_prompt_versions WHERE feature = %s ORDER BY version
            """,
            (name,),
        ).fetchall()
        last_eval = conn.execute(
            """
            SELECT * FROM aicp_eval_runs WHERE feature = %s
            ORDER BY created_at DESC LIMIT 1
            """,
            (name,),
        ).fetchone()
    return jsonable(
        {"feature": dict(feat), "prompts": [dict(p) for p in prompts], "last_eval": last_eval}
    )


@app.post("/features/{name}/kill")
def kill_feature(name: str) -> Any:
    with get_pool().connection() as conn:
        row = set_killed(conn, name, True)
    if row is None:
        return _error(404, "unknown_feature", f"unknown feature {name}")
    return {"feature": row, "killed": True}


@app.post("/features/{name}/unkill")
def unkill_feature(name: str) -> Any:
    with get_pool().connection() as conn:
        row = set_killed(conn, name, False)
    if row is None:
        return _error(404, "unknown_feature", f"unknown feature {name}")
    return {"feature": row, "killed": False}


@app.post("/features/{name}/prompts")
def add_prompt(name: str, body: PromptBody) -> Any:
    with get_pool().connection() as conn:
        if load_feature(conn, name) is None:
            return _error(404, "unknown_feature", f"unknown feature {name}")
        created = create_prompt_version(conn, name, body.body)
    return JSONResponse(status_code=201, content=created)


@app.post("/features/{name}/eval")
def eval_feature(name: str, body: EvalBody) -> Any:
    try:
        with get_pool().connection() as conn:
            return run_eval(conn, name, body.version, checkers=body.checkers)
    except KeyError:
        return _error(404, "unknown_version", "unknown version")


@app.post("/features/{name}/promote")
def promote_feature(name: str, body: PromoteBody) -> Any:
    try:
        with get_pool().connection() as conn:
            return promote(conn, name, body.version, body.eval_run_id)
    except KeyError as exc:
        return _error(404, "not_found", str(exc))
    except PermissionError as exc:
        code = str(exc)
        return _error(409, code, f"promote refused: {code}")


@app.get("/traces")
def traces(
    feature: str | None = None,
    tenant: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    sql = "SELECT * FROM aicp_traces WHERE 1=1"
    args: list[Any] = []
    if feature:
        sql += " AND feature = %s"
        args.append(feature)
    if tenant:
        sql += " AND tenant = %s"
        args.append(tenant)
    sql += " ORDER BY created_at DESC LIMIT %s"
    args.append(limit)
    with get_pool().connection() as conn:
        rows = conn.execute(sql, args).fetchall()
    return {"traces": jsonable([dict(r) for r in rows])}


@app.get("/traces/{trace_id}")
def trace_detail(trace_id: UUID) -> Any:
    with get_pool().connection() as conn:
        row = conn.execute("SELECT * FROM aicp_traces WHERE id = %s", (trace_id,)).fetchone()
    if row is None:
        return _error(404, "not_found", "unknown trace")
    return jsonable(dict(row))


@app.get("/budgets")
def budgets(tenant: str | None = None, feature: str | None = None) -> dict[str, Any]:
    sql = "SELECT * FROM aicp_budgets WHERE 1=1"
    args: list[Any] = []
    if tenant:
        sql += " AND tenant = %s"
        args.append(tenant)
    if feature:
        sql += " AND feature = %s"
        args.append(feature)
    sql += " ORDER BY window_start DESC, tenant, feature"
    with get_pool().connection() as conn:
        rows = conn.execute(sql, args).fetchall()
    return {"budgets": jsonable([dict(r) for r in rows])}


@app.get("/promotes")
def promotes(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    with get_pool().connection() as conn:
        rows = conn.execute(
            "SELECT * FROM aicp_promote_events ORDER BY created_at DESC LIMIT %s", (limit,)
        ).fetchall()
    return {"events": jsonable([dict(r) for r in rows])}


@app.get("/ops/snapshot")
def ops_snapshot() -> dict[str, Any]:
    with get_pool().connection() as conn:
        features = conn.execute(
            "SELECT name, killed, fail_closed, budget_requests FROM aicp_features"
        ).fetchall()
        traces = conn.execute("SELECT count(*) AS n FROM aicp_traces").fetchone()
        budgets = conn.execute(
            """
            SELECT coalesce(sum(request_count),0) AS requests,
                   coalesce(sum(spent_usd),0) AS spent
            FROM aicp_budgets
            """
        ).fetchone()
        last_eval = conn.execute(
            """
            SELECT feature, version, pass_rate, blocked, created_at
            FROM aicp_eval_runs
            ORDER BY created_at DESC LIMIT 5
            """
        ).fetchall()
    return jsonable(
        {
            "features": [dict(f) for f in features],
            "trace_count": traces["n"] if traces else 0,
            "budget": dict(budgets) if budgets else {},
            "recent_evals": [dict(r) for r in last_eval],
            "provider_mode": FAKE.mode,
            "provider_calls": FAKE.calls,
        }
    )


def _require_demo() -> None:
    if not settings.demo_mode:
        raise HTTPException(
            status_code=404, detail={"code": "not_found", "message": "demo mode off"}
        )


@app.get("/demo/provider")
def demo_provider() -> dict[str, Any]:
    _require_demo()
    return {"mode": FAKE.mode, "calls": FAKE.calls, "delay_ms": FAKE.delay_ms}


@app.post("/demo/provider")
def demo_set_provider(body: ProviderBody) -> Any:
    _require_demo()
    allowed = {"ok", "fail", "fail_once", "rate_limit", "slow"}
    if body.mode not in allowed:
        return _error(400, "bad_mode", f"mode must be one of {sorted(allowed)}")
    FAKE.mode = body.mode
    if body.delay_ms is not None:
        FAKE.delay_ms = body.delay_ms
    if body.mode != "fail_once":
        FAKE.fail_times = 0
    return {"mode": FAKE.mode, "delay_ms": FAKE.delay_ms, "calls": FAKE.calls}


@app.post("/demo/reset-lab")
def demo_reset() -> dict[str, str]:
    _require_demo()
    with get_pool().connection() as conn:
        restore_lab_runtime(conn)
    FAKE.reset()
    return {"status": "reset"}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    path = Path(__file__).with_name("static") / "index.html"
    return path.read_text(encoding="utf-8")


def main() -> None:
    cfg = load_settings()
    uvicorn.run(
        "aicp.api:app",
        host=cfg.api_host,
        port=cfg.api_port,
        reload=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
