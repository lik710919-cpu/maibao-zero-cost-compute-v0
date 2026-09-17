#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def sum_squares_upto(value: int) -> int:
    if value <= 0:
        return 0
    return value * (value + 1) * (2 * value + 1) // 6


def sum_squares_formula(start: int, end: int) -> int:
    return sum_squares_upto(end) - sum_squares_upto(start - 1)


def fail(message: str) -> None:
    raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    result_paths = sorted(Path(args.results_dir).glob("result-*.json"))
    if len(result_paths) != 4:
        fail(f"expected exactly 4 worker results, found {len(result_paths)}")

    results = [json.loads(path.read_text(encoding="utf-8")) for path in result_paths]
    results.sort(key=lambda item: item["chunk_index"])

    indexes = [item["chunk_index"] for item in results]
    if indexes != [0, 1, 2, 3]:
        fail(f"invalid chunk indexes: {indexes}")

    n_values = {item["n"] for item in results}
    chunks_values = {item["chunks"] for item in results}
    if len(n_values) != 1 or chunks_values != {4}:
        fail("workers disagree about n or chunk count")
    n = n_values.pop()

    expected_start = 1
    combined = 0
    for item in results:
        start = item["range_start"]
        end = item["range_end"]
        if start != expected_start or end < start:
            fail(f"range coverage failure at chunk {item['chunk_index']}")
        expected_start = end + 1

        if item["runner_environment"] != "github-hosted":
            fail("worker was not GitHub-hosted")
        if item["repo_visibility"] != "public":
            fail("worker did not run from a public repository")
        if item.get("local_compute_used") is not False:
            fail("local formal compute was reported")

        partial = item["partial_sum"]
        if partial != sum_squares_formula(start, end):
            fail(f"partial result mismatch for chunk {item['chunk_index']}")
        combined += partial

    if expected_start != n + 1:
        fail("worker ranges do not cover 1..N exactly")

    expected_total = sum_squares_formula(1, n)
    if combined != expected_total:
        fail("combined result does not equal closed-form result")

    hostnames = sorted({item["hostname"] for item in results})
    runner_names = sorted({item["runner_name"] for item in results})
    evidence = {
        "status": "PASS",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "formal_compute_location": "external-github-hosted-only",
        "local_formal_compute_percent": 0,
        "repository_visibility": "public",
        "worker_count": 4,
        "n": n,
        "combined_sum": combined,
        "expected_sum": expected_total,
        "unique_hostnames": hostnames,
        "unique_hostname_count": len(hostnames),
        "unique_runner_names": runner_names,
        "unique_runner_name_count": len(runner_names),
        "workers": results,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "verification.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8"
    )

    lines = [
        "# Zero-Cash-Cost External Compute V0 Verification",
        "",
        "- Status: PASS",
        "- Local formal compute: 0%",
        "- Formal compute: GitHub-hosted external runners only",
        "- Repository visibility: public",
        f"- Worker count: 4",
        f"- N: {n}",
        f"- Combined sum: {combined}",
        f"- Expected sum: {expected_total}",
        f"- Unique hostnames observed: {len(hostnames)}",
        f"- Unique runner names observed: {len(runner_names)}",
        "",
        "## Worker evidence",
    ]
    for item in results:
        lines.append(
            f"- chunk {item['chunk_index']}: {item['range_start']}..{item['range_end']}; "
            f"host={item['hostname']}; runner={item['runner_name']}; "
            f"duration={item['duration_seconds']}s"
        )
    (output_dir / "verification.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
