#!/usr/bin/env python3
import argparse
import json
import os
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from compute_chunk import partition_range, sum_squares_formula

WANDBOX_EXECUTE_URL = "https://wandbox.org/api/compile.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_remote_code(start: int, end: int, challenge: str) -> str:
    return (
        "import json\n"
        "total = 0\n"
        f"for value in range({start}, {end + 1}):\n"
        "    total += value * value\n"
        f"print(json.dumps({{'challenge': {challenge!r}, 'partial_sum': total}}))\n"
    )


def parse_wandbox_response(raw: dict, expected_challenge: str) -> dict:
    if str(raw.get("status", "")) != "0":
        raise RuntimeError(f"Wandbox execution failed with status {raw.get('status')!r}")
    output = str(raw.get("program_output", "")).strip().splitlines()
    if not output:
        raise RuntimeError("Wandbox returned no program output")
    try:
        payload = json.loads(output[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError("Wandbox returned invalid JSON output") from exc
    if payload.get("challenge") != expected_challenge:
        raise RuntimeError("Wandbox challenge mismatch")
    if not isinstance(payload.get("partial_sum"), int):
        raise RuntimeError("Wandbox partial_sum is not an integer")
    return payload


def execute_remote(compiler: str, code: str, timeout_seconds: int = 30) -> dict:
    body = json.dumps({"compiler": compiler, "code": code}).encode("utf-8")
    request = urllib.request.Request(
        WANDBOX_EXECUTE_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "maibao-zero-cost-compute-v3/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Wandbox request failed: {exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--chunks", type=int, required=True)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if os.getenv("REPO_VISIBILITY", "") != "public":
        raise RuntimeError("V3 zero-cash-cost proof requires a public repository")

    start, end = partition_range(args.n, args.chunks, args.index)
    challenge = secrets.token_hex(16)
    started_at = utc_now()
    raw = execute_remote(args.compiler, build_remote_code(start, end, challenge))
    parsed = parse_wandbox_response(raw, challenge)
    finished_at = utc_now()

    expected = sum_squares_formula(start, end)
    if parsed["partial_sum"] != expected:
        raise RuntimeError("Wandbox worker self-check failed")

    run_id = os.getenv("GITHUB_RUN_ID", "unknown")
    result = {
        "chunk_index": args.index,
        "chunks": args.chunks,
        "n": args.n,
        "range_start": start,
        "range_end": end,
        "partial_sum": parsed["partial_sum"],
        "attempt": "primary",
        "provider_id": "wandbox-public",
        "provider_evidence": f"real:wandbox:{run_id}:{challenge[:12]}",
        "runner_environment": "wandbox-public-api",
        "runner_name": "wandbox-public",
        "runner_os": "remote",
        "runner_arch": "remote",
        "hostname": "wandbox.org",
        "platform_node": "wandbox.org",
        "cpu_count": None,
        "repo_visibility": "public",
        "github_run_id": run_id,
        "github_run_attempt": os.getenv("GITHUB_RUN_ATTEMPT", ""),
        "github_sha": os.getenv("GITHUB_SHA", ""),
        "wandbox_compiler": args.compiler,
        "wandbox_status": str(raw.get("status", "")),
        "started_at": started_at,
        "finished_at": finished_at,
        "local_compute_used": False,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
