# Zero-Cash-Cost External Compute V1 Closed-Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn V0 into an automatically sharded, self-healing, externally verified zero-cash-cost compute loop.

**Architecture:** Add an external planning stage that chooses shard count and emits a matrix; primary workers compute shards; a repair planner validates primary artifacts and emits only missing/invalid indexes; repair workers recompute those shards; the final external aggregator validates exact coverage and correctness and writes closure evidence.

**Tech Stack:** Python 3 standard library, GitHub Actions, standard GitHub-hosted `ubuntu-latest` runners, Actions artifacts.

**Spec:** `docs/superpowers/specs/2026-09-17-zero-cost-compute-v1-closed-loop-design.md`

## Global Constraints
- Local formal compute contribution is 0%.
- Public repository and standard GitHub-hosted runners only.
- Acceptance run cash compute cost is 0.
- No secrets, private data, production code, paid cloud resources, or larger runners.
- One deliberately failed primary shard must be repaired automatically.

---

### Task 1: RED tests for automatic planning and recovery
**Files:** modify `experiments/zero_cost_compute_v0/tests/test_compute.py`; create `experiments/zero_cost_compute_v0/tests/test_closed_loop.py`.

- [ ] Add tests asserting automatic shard count: 40,000,000 / 5,000,000 => 8; cap behavior; minimum one shard.
- [ ] Add a test that creates primary results with one missing shard and asserts the recovery planner returns exactly that index.
- [ ] Add a dynamic aggregation test using three valid shards plus one repair result and assert final PASS and repaired index evidence.
- [ ] Run `python -m unittest discover -s experiments/zero_cost_compute_v0/tests -v` remotely on a GitHub-hosted runner and capture the expected RED failure before implementation.

### Task 2: Automatic planner and repair planner
**Files:** create `experiments/zero_cost_compute_v0/plan_work.py`; create `experiments/zero_cost_compute_v0/plan_repairs.py`; modify `compute_chunk.py`.

- [ ] Implement `choose_chunk_count(n, target_items_per_chunk, max_chunks)` using ceiling division and cap.
- [ ] Emit JSON indexes plus GitHub job outputs from `plan_work.py`.
- [ ] Add `--attempt` to `compute_chunk.py` and record `primary` or `repair` in worker evidence.
- [ ] Implement validation of primary artifacts in `plan_repairs.py`; missing or invalid indexes become repair indexes; use a no-op sentinel only when no repairs are required.
- [ ] Re-run the full unit suite remotely and require GREEN.

### Task 3: Dynamic aggregation and self-healing workflow
**Files:** modify `aggregate_results.py`; create `.github/workflows/zero-cost-compute-v1.yml`.

- [ ] Refactor aggregation to accept expected N and chunk count dynamically and prefer a repair result only for an index missing/invalid in primary results.
- [ ] Emit evidence fields: `automatic_chunk_count`, `primary_valid_count`, `repaired_result_count`, `recovered_indexes`, `local_formal_compute_percent`, totals, runner evidence, and PASS.
- [ ] Workflow planner job emits dynamic matrix.
- [ ] Primary matrix uses planner output and job-level tolerance so one shard can fail without stopping repair planning.
- [ ] Acceptance input injects failure for primary shard 2 before formal computation.
- [ ] Repair planner downloads primary artifacts and emits only missing/invalid indexes.
- [ ] Repair matrix recomputes those indexes externally.
- [ ] Aggregate job downloads primary + repair artifacts, runs unit tests, verifies complete result, and uploads final evidence.

### Task 4: Real acceptance, integration, permanent closure
**Files:** update `README.md`; create repository closure issue after success.

- [ ] Open a pull request from `experiment/zero-cost-compute-v1-closed-loop` to `main`.
- [ ] Run the V1 workflow on the feature branch with N=40,000,000, target=5,000,000, max=16, injected failure index=2; require automatic 8-shard plan and successful repair.
- [ ] Merge only after evidence is green.
- [ ] Run a fresh acceptance from `main` and verify all jobs, steps, artifacts, and evidence.
- [ ] Store permanent closure issue with run ID, commit SHA, chunk count, recovered index, final totals, zero-local-compute evidence, and artifact digest; close it as completed.
