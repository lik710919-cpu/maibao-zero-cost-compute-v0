#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Callable

from routed_chunk import github_compute_result, wandbox_compute_result


def execute_assigned_provider(
    provider_id: str,
    github_executor: Callable[[], dict],
    wandbox_executor: Callable[[], dict],
) -> dict:
    if provider_id == "github-actions-public":
        result = github_executor()
    elif provider_id == "wandbox-public":
        result = wandbox_executor()
    else:
        raise RuntimeError(f"no assigned executor for provider {provider_id}")

    actual_provider = result.get("provider_id")
    if actual_provider != provider_id:
        raise RuntimeError(
            f"assigned provider identity mismatch: expected {provider_id}, got {actual_provider}"
        )
    result = dict(result)
    result["scheduled_provider_id"] = provider_id
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--chunks", type=int, required=True)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    result = execute_assigned_provider(
        args.provider,
        lambda: github_compute_result(args.n, args.chunks, args.index),
        lambda: wandbox_compute_result(args.n, args.chunks, args.index, args.compiler),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
