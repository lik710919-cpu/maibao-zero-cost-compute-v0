#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def fail(message: str) -> None:
    raise RuntimeError(message)


def verify_dispatch(result_paths: list[Path]) -> dict:
    items = [json.loads(Path(path).read_text(encoding="utf-8")) for path in result_paths]
    if len(items) != 2:
        fail(f"expected exactly 2 routed results, got {len(items)}")
    items.sort(key=lambda item: item.get("chunk_index", -1))

    route = ["github-actions-public", "wandbox-public"]
    for item in items:
        if item.get("dispatch_route") != route:
            fail("runtime route does not match expected ranked provider route")

    first, second = items
    if first.get("provider_id") != "github-actions-public":
        fail("shard 0 did not use the primary provider")
    if first.get("failover_used") is not False:
        fail("shard 0 unexpectedly used failover")
    if first.get("dispatch_attempts") != [
        {"provider_id": "github-actions-public", "status": "success"}
    ]:
        fail("shard 0 dispatch evidence is invalid")

    attempts = second.get("dispatch_attempts")
    if second.get("provider_id") != "wandbox-public":
        fail("shard 1 did not land on the fallback provider")
    if second.get("failover_used") is not True:
        fail("shard 1 did not record failover")
    if not isinstance(attempts, list) or len(attempts) != 2:
        fail("shard 1 dispatch attempt count is invalid")
    if attempts[0].get("provider_id") != "github-actions-public" or attempts[0].get("status") != "failed":
        fail("shard 1 did not record the primary provider failure")
    if "controlled provider failure" not in attempts[0].get("error", ""):
        fail("shard 1 primary failure was not the controlled acceptance failure")
    if attempts[1] != {"provider_id": "wandbox-public", "status": "success"}:
        fail("shard 1 fallback success evidence is invalid")

    provider_ids = sorted({item.get("provider_id") for item in items})
    evidence = {
        "status": "PASS",
        "route_primary": route[0],
        "route_fallbacks": route[1:],
        "normal_shard_provider": first.get("provider_id"),
        "failed_primary_provider": attempts[0].get("provider_id"),
        "fallback_shard_provider": second.get("provider_id"),
        "failover_used": True,
        "execution_provider_ids": provider_ids,
        "execution_provider_count": len(provider_ids),
        "local_formal_compute_percent": 0,
    }
    if provider_ids != route:
        fail("final execution providers do not match the two-provider acceptance route")
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    paths = sorted(Path(args.results_dir).rglob("result-*.json"))
    evidence = verify_dispatch(paths)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
