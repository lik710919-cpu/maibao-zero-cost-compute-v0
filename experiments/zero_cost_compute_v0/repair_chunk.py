#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Callable

from routed_chunk import github_compute_result, wandbox_compute_result


def execute_repair(
    original_provider_id: str,
    provider_id: str,
    executor: Callable[[], dict],
) -> dict:
    if not original_provider_id or not provider_id:
        raise RuntimeError("repair provider identities must be non-empty")
    if original_provider_id == provider_id:
        raise RuntimeError("repair must use a different provider")

    raw = executor()
    if raw.get("provider_id") != provider_id:
        raise RuntimeError(
            f"repair provider identity mismatch: expected {provider_id}, got {raw.get('provider_id')}"
        )
    if raw.get("local_compute_used") is not False:
        raise RuntimeError("repair result must not use local formal compute")

    result = dict(raw)
    result["attempt"] = "repair"
    result["scheduled_provider_id"] = provider_id
    result["original_provider_id"] = original_provider_id
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--chunks", type=int, required=True)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--original-provider", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    def executor() -> dict:
        if args.provider == "wandbox-public":
            return wandbox_compute_result(args.n, args.chunks, args.index, args.compiler)
        if args.provider == "github-actions-public":
            return github_compute_result(args.n, args.chunks, args.index)
        raise RuntimeError(f"no repair executor for provider {args.provider}")

    result = execute_repair(args.original_provider, args.provider, executor)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
