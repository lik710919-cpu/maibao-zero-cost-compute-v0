#!/usr/bin/env python3
import argparse
import json
import os
import platform
import secrets
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from compute_chunk import (
    compute_iteratively,
    partition_range,
    require_external_zero_cash_context,
    sum_squares_formula,
)
from provider_dispatch import dispatch_with_failover
from provider_model import ProviderSnapshot
from provider_router import route_provider
from wandbox_chunk import build_remote_code, execute_remote, parse_wandbox_response

WANDBOX_LIST_URL = "https://wandbox.org/api/list.json"
WANDBOX_V3_PROOF = "real:wandbox:main-v3:35193523068"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def probe_wandbox_compiler(compiler: str, timeout_seconds: int = 15) -> bool:
    request = urllib.request.Request(
        WANDBOX_LIST_URL,
        headers={"User-Agent": "maibao-zero-cost-compute-v4/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return False
    return any(
        isinstance(item, dict) and item.get("name") == compiler
        for item in payload
        if isinstance(payload, list)
    )


def build_runtime_route(compiler: str) -> tuple[dict, list[ProviderSnapshot]]:
    run_id = os.getenv("GITHUB_RUN_ID", "")
    github_ready = (
        os.getenv("GITHUB_ACTIONS", "") == "true"
        and os.getenv("RUNNER_ENVIRONMENT", "") == "github-hosted"
        and os.getenv("REPO_VISIBILITY", "") == "public"
        and bool(run_id)
    )
    github = ProviderSnapshot(
        "github-actions-public",
        github_ready,
        github_ready,
        github_ready,
        0.0,
        os.cpu_count() or 1,
        f"run:{run_id}" if github_ready else "none",
        "ready" if github_ready else "not_eligible",
    )

    wandbox_healthy = probe_wandbox_compiler(compiler)
    wandbox = ProviderSnapshot(
        "wandbox-public",
        True,
        wandbox_healthy,
        wandbox_healthy,
        0.0,
        1,
        WANDBOX_V3_PROOF if wandbox_healthy else "none",
        "ready" if wandbox_healthy else "unhealthy",
    )
    providers = [github, wandbox]
    return route_provider(providers), providers


def github_compute_result(n: int, chunks: int, index: int) -> dict:
    require_external_zero_cash_context()
    start, end = partition_range(n, chunks, index)
    started_at = utc_now()
    started = time.perf_counter()
    partial_sum = compute_iteratively(start, end)
    duration = time.perf_counter() - started
    finished_at = utc_now()
    if partial_sum != sum_squares_formula(start, end):
        raise RuntimeError("GitHub worker self-check failed")
    return {
        "chunk_index": index,
        "chunks": chunks,
        "n": n,
        "range_start": start,
        "range_end": end,
        "partial_sum": partial_sum,
        "attempt": "primary",
        "provider_id": "github-actions-public",
        "provider_evidence": f"run:{os.getenv('GITHUB_RUN_ID', '')}",
        "hostname": socket.gethostname(),
        "platform_node": platform.node(),
        "cpu_count": os.cpu_count(),
        "runner_name": os.getenv("RUNNER_NAME", ""),
        "runner_environment": os.getenv("RUNNER_ENVIRONMENT", ""),
        "runner_os": os.getenv("RUNNER_OS", ""),
        "runner_arch": os.getenv("RUNNER_ARCH", ""),
        "repo_visibility": os.getenv("REPO_VISIBILITY", ""),
        "github_run_id": os.getenv("GITHUB_RUN_ID", ""),
        "github_run_attempt": os.getenv("GITHUB_RUN_ATTEMPT", ""),
        "github_sha": os.getenv("GITHUB_SHA", ""),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(duration, 6),
        "local_compute_used": False,
    }


def wandbox_compute_result(n: int, chunks: int, index: int, compiler: str) -> dict:
    if os.getenv("REPO_VISIBILITY", "") != "public":
        raise RuntimeError("Wandbox fallback requires a public repository")
    start, end = partition_range(n, chunks, index)
    challenge = secrets.token_hex(16)
    started_at = utc_now()
    raw = execute_remote(compiler, build_remote_code(start, end, challenge))
    parsed = parse_wandbox_response(raw, challenge)
    finished_at = utc_now()
    expected = sum_squares_formula(start, end)
    if parsed["partial_sum"] != expected:
        raise RuntimeError("Wandbox fallback self-check failed")
    run_id = os.getenv("GITHUB_RUN_ID", "unknown")
    return {
        "chunk_index": index,
        "chunks": chunks,
        "n": n,
        "range_start": start,
        "range_end": end,
        "partial_sum": parsed["partial_sum"],
        "attempt": "primary",
        "provider_id": "wandbox-public",
        "provider_evidence": f"real:wandbox:{run_id}:{challenge[:12]}",
        "hostname": "wandbox.org",
        "platform_node": "wandbox.org",
        "cpu_count": None,
        "runner_name": "wandbox-public",
        "runner_environment": "wandbox-public-api",
        "runner_os": "remote",
        "runner_arch": "remote",
        "repo_visibility": "public",
        "github_run_id": run_id,
        "github_run_attempt": os.getenv("GITHUB_RUN_ATTEMPT", ""),
        "github_sha": os.getenv("GITHUB_SHA", ""),
        "wandbox_compiler": compiler,
        "wandbox_status": str(raw.get("status", "")),
        "started_at": started_at,
        "finished_at": finished_at,
        "local_compute_used": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--chunks", type=int, required=True)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--inject-provider-failure", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    route, snapshots = build_runtime_route(args.compiler)
    injected = args.inject_provider_failure.strip()

    def execute(provider_id: str) -> dict:
        if provider_id == injected:
            raise RuntimeError(f"controlled provider failure: {provider_id}")
        if provider_id == "github-actions-public":
            return github_compute_result(args.n, args.chunks, args.index)
        if provider_id == "wandbox-public":
            return wandbox_compute_result(args.n, args.chunks, args.index, args.compiler)
        raise RuntimeError(f"no executor for provider {provider_id}")

    result = dispatch_with_failover(route, execute)
    result["routing_snapshots"] = [
        {
            "provider_id": item.provider_id,
            "healthy": item.healthy,
            "zero_cash_cost": item.zero_cash_cost,
            "queue_seconds": item.queue_seconds,
            "capacity": item.capacity,
            "status": item.status,
        }
        for item in snapshots
    ]

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
