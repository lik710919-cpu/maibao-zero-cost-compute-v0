# Zero-Cash-Cost External Compute V0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and prove a five-job external compute loop in which four GitHub-hosted workers perform all formal computation and a fifth GitHub-hosted job aggregates and verifies the result.

**Architecture:** A public repository branch push ignites a GitHub Actions matrix with four workers. Workers compute disjoint sum-of-squares ranges and upload JSON artifacts; an aggregate job downloads all artifacts, validates structure and correctness, and uploads final evidence.

**Tech Stack:** Python 3 standard library, GitHub Actions, `actions/checkout@v4`, `actions/upload-artifact@v4`, `actions/download-artifact@v4`.

**Spec:** `docs/superpowers/specs/2026-09-17-zero-cost-compute-v0-design.md`

## Global Constraints
- Local formal compute contribution must remain 0%.
- Repository must remain public and contain no secrets or production data.
- Only standard GitHub-hosted runners are allowed.
- Experiment must fail closed on missing or incorrect worker evidence.
- No paid cloud services or non-standard paid runners.

---

### Task 1: Computation core and tests

**Files:**
- Create: `experiments/zero_cost_compute_v0/compute_chunk.py`
- Create: `experiments/zero_cost_compute_v0/tests/test_compute.py`

**Interfaces:**
- Produces: `partition_range(n, chunks, index) -> tuple[int, int]`, `sum_squares_formula(start, end) -> int`, worker JSON result.

- [ ] Write tests for exact partition coverage, no overlap, and formula correctness.
- [ ] Implement partitioning and iterative partial computation.
- [ ] Make each worker self-check its iterative result against the range formula.
- [ ] Record runner and timing evidence in JSON.

### Task 2: External aggregation verifier

**Files:**
- Create: `experiments/zero_cost_compute_v0/aggregate_results.py`

**Interfaces:**
- Consumes: four `result-*.json` worker artifacts.
- Produces: `evidence/verification.json` and `evidence/verification.md`.

- [ ] Require exactly four unique chunks.
- [ ] Validate contiguous coverage of 1..N.
- [ ] Validate public repository visibility and GitHub-hosted runner environment.
- [ ] Sum partial results and compare with the closed-form expected total.
- [ ] Emit evidence only on complete success.

### Task 3: Remote workflow and real run

**Files:**
- Create: `.github/workflows/zero-cost-compute-v0.yml`
- Create: `experiments/zero_cost_compute_v0/README.md`

**Interfaces:**
- Push to `experiment/zero-cost-compute-v0` or `main` starts the experiment.
- Matrix indexes: 0, 1, 2, 3.

- [ ] Use `ubuntu-latest` and `max-parallel: 4`.
- [ ] Upload one artifact per worker.
- [ ] Run unit tests in the aggregate job.
- [ ] Download all worker artifacts with `merge-multiple: true`.
- [ ] Run the aggregate verifier.
- [ ] Upload final evidence artifact.
- [ ] Inspect the real run, jobs, steps, logs, and artifacts.
- [ ] Merge only after the experiment is green and evidence is complete.