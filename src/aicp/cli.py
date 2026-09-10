from __future__ import annotations

import argparse
import json
import sys
from uuid import UUID

import httpx

from aicp.config import load_settings


def _base() -> str:
    settings = load_settings()
    host = "127.0.0.1" if settings.api_host in {"0.0.0.0", "::"} else settings.api_host
    return f"http://{host}:{settings.api_port}"


def _client() -> httpx.Client:
    return httpx.Client(base_url=_base(), timeout=15.0)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="aicp",
        description="CLI for the AI reliability control plane (not a chatbot)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    complete = sub.add_parser("complete")
    complete.add_argument("feature")
    complete.add_argument("--tenant", required=True)
    complete.add_argument("--input", required=True)
    complete.add_argument("--timeout-ms", type=int)

    ev = sub.add_parser("eval")
    ev.add_argument("feature")
    ev.add_argument("version", type=int)

    promo = sub.add_parser("promote")
    promo.add_argument("feature")
    promo.add_argument("version", type=int)
    promo.add_argument("--eval-id", required=True)

    kill = sub.add_parser("kill")
    kill.add_argument("feature")
    unk = sub.add_parser("unkill")
    unk.add_argument("feature")

    bud = sub.add_parser("budget")
    bud.add_argument("--tenant")
    bud.add_argument("--feature")

    tr = sub.add_parser("traces")
    tr.add_argument("--feature")
    tr.add_argument("--tenant")
    tr.add_argument("--limit", type=int, default=20)

    gett = sub.add_parser("trace")
    gett.add_argument("trace_id")

    sub.add_parser("features")
    sub.add_parser("health")

    args = parser.parse_args(argv)
    with _client() as client:
        if args.cmd == "complete":
            payload: dict[str, object] = {
                "feature": args.feature,
                "tenant": args.tenant,
                "input": args.input,
            }
            if args.timeout_ms:
                payload["timeout_ms"] = args.timeout_ms
            resp = client.post("/complete", json=payload)
        elif args.cmd == "eval":
            resp = client.post(f"/features/{args.feature}/eval", json={"version": args.version})
        elif args.cmd == "promote":
            resp = client.post(
                f"/features/{args.feature}/promote",
                json={"version": args.version, "eval_run_id": str(UUID(args.eval_id))},
            )
        elif args.cmd == "kill":
            resp = client.post(f"/features/{args.feature}/kill")
        elif args.cmd == "unkill":
            resp = client.post(f"/features/{args.feature}/unkill")
        elif args.cmd == "budget":
            params: dict[str, str] = {}
            if args.tenant:
                params["tenant"] = args.tenant
            if args.feature:
                params["feature"] = args.feature
            resp = client.get("/budgets", params=params)
        elif args.cmd == "traces":
            params = {}
            if args.feature:
                params["feature"] = args.feature
            if args.tenant:
                params["tenant"] = args.tenant
            params["limit"] = str(args.limit)
            resp = client.get("/traces", params=params)
        elif args.cmd == "trace":
            resp = client.get(f"/traces/{args.trace_id}")
        elif args.cmd == "features":
            resp = client.get("/features")
        elif args.cmd == "health":
            resp = client.get("/health")
        else:
            parser.error("unknown command")
            return
        sys.stdout.write(json.dumps(resp.json(), indent=2, default=str) + "\n")
        if resp.status_code >= 400:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
