# Maibao Zero-Cash-Cost External Compute V0

This experiment proves a minimal external distributed-compute loop with zero local formal computation.

## Boundary
- The local machine may only create/trigger the experiment and inspect returned evidence.
- All formal workload execution occurs on standard GitHub-hosted runners.
- The repository is public and contains only synthetic workload code/data.
- No production code, secrets, private data, paid cloud services, or paid runner classes are used.

## Real experiment
One workflow run creates four matrix worker jobs. Each worker receives one non-overlapping section of `1..N`, iteratively computes the sum of squares for that section, self-checks it, and uploads a JSON result artifact.

A fifth external job downloads all four results, verifies exact coverage and correctness against the closed-form formula, verifies external/public execution constraints, and uploads the final evidence artifact.

## Pass condition
`verification.json` must contain `status: PASS`, `local_formal_compute_percent: 0`, `worker_count: 4`, and identical combined/expected sums. Any missing or invalid worker result fails the workflow.
