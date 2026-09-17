# Zero-Cash-Cost External Compute V0 Design

## Goal
Prove that a local machine can act only as the ignition/control point while all formal computation is performed by external, zero-cash-cost, GitHub-hosted runners in a public repository.

## Frozen constraints
- Local machine contributes 0% of formal computation.
- Repository contains only synthetic, non-sensitive test data and code.
- Cash cost must be 0 for the experiment.
- Use only standard GitHub-hosted runners in a public repository.
- No paid cloud resources, secrets, production code, or private data.
- The first closed loop is: split -> parallel external compute -> artifact return -> external aggregation -> deterministic verification.

## Architecture
A push to the experiment branch is the ignition event. A matrix job creates four independent worker jobs on `ubuntu-latest`. Each worker receives one disjoint integer range, computes the sum of squares using a real Python loop, self-checks the partial result, and uploads a JSON artifact containing the result and runner evidence.

A fifth GitHub-hosted job downloads all four artifacts, validates partition coverage, validates the combined result against the closed-form sum-of-squares formula, verifies the repository is public and the workers are GitHub-hosted, then emits a machine-readable and human-readable evidence artifact.

## Workload
For integer N, partition [1, N] into four contiguous, non-overlapping ranges. Each worker computes `sum(i*i for i in its range)` by iteration. The aggregator validates the combined value against `N*(N+1)*(2*N+1)//6`.

The workload is deliberately synthetic: it proves remote compute and result aggregation without exposing project data.

## Evidence requirements
Each worker records chunk index, range, partial sum, hostname, runner name, runner environment, operating system, architecture, CPU count, start/end time, duration, repository visibility, run ID, and commit SHA.

The aggregator must prove:
1. exactly four worker results exist;
2. chunk indexes are 0..3 exactly once;
3. ranges are contiguous and cover 1..N with no gaps or overlaps;
4. combined sum equals the closed-form expected value;
5. every worker reports a GitHub-hosted runner;
6. repository visibility is public;
7. no worker reports local execution.

## Failure model
Any missing, duplicate, malformed, overlapping, or incorrect worker result makes aggregation fail. No partial success is accepted.

## V0 success criterion
The experiment is complete only when a real GitHub Actions run finishes successfully, all four worker jobs produce artifacts, the external aggregation job verifies the final answer, and the evidence artifact is retrievable from the run.