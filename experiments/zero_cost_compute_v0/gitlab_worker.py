#!/usr/bin/env python3
import argparse
import json
import os
import platform
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


PROVIDER_ID = "gitlab-hosted-runners"
EXPECTED_RUNNER_TAG = "saas-linux-small-amd64"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sum_squares_upto(value: int) -> int:
    if value <= 0:
        return 0
    return value * (value + 1) * (2 * value + 1) // 6


def expected_sum(start: int, end: int) -> int:
    return sum_squares_upto(end) - sum_squares_upto(start - 1)


def _positive_int(env: Mapping[str, str], key: str) -> int:
    raw = env.get(key, "")
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{key} must be a positive integer") from exc
    if value <= 0:
        raise RuntimeError(f"{key} must be a positive integer")
    return value


def require_gitlab_hosted_context(env: Mapping[str, str]) -> tuple[int, int, int]:
    if env.get("GITLAB_CI") != "true":
        raise RuntimeError("GITLAB_CI must be true")
    if env.get("CI_SERVER_HOST") != "gitlab.com":
        raise RuntimeError("formal GitLab provider must run on gitlab.com")
    runner_tags = env.get("CI_RUNNER_TAGS", "")
    if EXPECTED_RUNNER_TAG not in runner_tags:
        raise RuntimeError("formal compute must use the GitLab-hosted small Linux runner")
    pipeline_id = _positive_int(env, "CI_PIPELINE_ID")
    job_id = _positive_int(env, "CI_JOB_ID")
    runner_id = _positive_int(env, "CI_RUNNER_ID")
    return pipeline_id, job_id, runner_id


def compute_result(
    index: int,
    start: int,
    end: int,
    nonce: str,
    env: Mapping[str, str],
) -> dict:
    if not isinstance(index, int) or index < 0:
        raise ValueError("invalid chunk index")
    if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start:
        raise ValueError("invalid range")
    if not isinstance(nonce, str) or not nonce or len(nonce) > 128:
        raise ValueError("invalid nonce")

    pipeline_id, job_id, runner_id = require_gitlab_hosted_context(env)
    started_at = utc_now()
    started = time.perf_counter()
    total = 0
    for value in range(start, end + 1):
        total += value * value
    duration = time.perf_counter() - started
    finished_at = utc_now()

    if total != expected_sum(start, end):
        raise RuntimeError("worker self-check failed")

    return {
        "provider_id": PROVIDER_ID,
        "pipeline_id": pipeline_id,
        "job_id": job_id,
        "runner_id": runner_id,
        "runner_description": env.get("CI_RUNNER_DESCRIPTION", ""),
        "runner_tags": env.get("CI_RUNNER_TAGS", ""),
        "server_host": env.get("CI_SERVER_HOST", ""),
        "chunk_index": index,
        "range_start": start,
        "range_end": end,
        "nonce": nonce,
        "partial_sum": total,
        "hostname": socket.gethostname(),
        "platform_node": platform.node(),
        "cpu_count": os.cpu_count(),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(duration, 6),
        "local_compute_used": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--nonce", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    result = compute_result(args.index, args.start, args.end, args.nonce, os.environ)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
