#!/usr/bin/env python3
import argparse
import json
import os
import platform
import socket
import time
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sum_squares_upto(value: int) -> int:
    if value <= 0:
        return 0
    return value * (value + 1) * (2 * value + 1) // 6


def sum_squares_formula(start: int, end: int) -> int:
    if start < 1 or end < start:
        raise ValueError("invalid range")
    return sum_squares_upto(end) - sum_squares_upto(start - 1)


def partition_range(n: int, chunks: int, index: int) -> tuple[int, int]:
    if n < 1:
        raise ValueError("n must be positive")
    if chunks < 1 or not 0 <= index < chunks:
        raise ValueError("invalid chunk configuration")
    if n < chunks:
        raise ValueError("n must be at least chunks")
    base, remainder = divmod(n, chunks)
    size = base + (1 if index < remainder else 0)
    start = 1 + index * base + min(index, remainder)
    return start, start + size - 1


def require_external_zero_cash_context() -> None:
    checks = {
        "GITHUB_ACTIONS": "true",
        "RUNNER_ENVIRONMENT": "github-hosted",
        "REPO_VISIBILITY": "public",
    }
    for key, expected in checks.items():
        actual = os.getenv(key, "")
        if actual != expected:
            raise RuntimeError(f"{key} must be {expected!r}, got {actual!r}")


def compute_iteratively(start: int, end: int) -> int:
    total = 0
    for value in range(start, end + 1):
        total += value * value
    return total


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--chunks", type=int, required=True)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    require_external_zero_cash_context()
    start, end = partition_range(args.n, args.chunks, args.index)
    started_at = utc_now()
    started = time.perf_counter()
    partial_sum = compute_iteratively(start, end)
    duration = time.perf_counter() - started
    finished_at = utc_now()

    expected = sum_squares_formula(start, end)
    if partial_sum != expected:
        raise RuntimeError("worker self-check failed")

    result = {
        "chunk_index": args.index,
        "chunks": args.chunks,
        "n": args.n,
        "range_start": start,
        "range_end": end,
        "partial_sum": partial_sum,
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

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
