# Zero-Cost Compute V6 Self-Healing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add cross-provider self-healing to the V5 adaptive pool so one failed GitHub-hosted shard is detected and only that shard is recomputed once on the reserved Wandbox provider.

**Architecture:** V6 is isolated from V5. A recovery plan reserves Wandbox's single formal-work budget and schedules all eight primary shards to GitHub. The workflow injects a controlled pre-compute failure at shard 4, a repair planner validates the seven surviving primary results and emits only shard 4, a repair executor sends that shard to Wandbox, and a recovery verifier proves that exactly seven primary results plus one repair result formed the final answer.

**Tech Stack:** Python 3 standard library, GitHub Actions hosted runners, Wandbox public API, JSON artifacts, unittest.

**Spec:** `docs/superpowers/specs/2026-09-17-zero-cost-compute-v6-self-healing-design.md`

## Global Constraints

- Local formal compute remains exactly 0%.
- V1-V5 existing workflows and modules remain unchanged unless a shared validation bug is discovered and independently regression-tested.
- Wandbox formal-work budget is exactly one shard per V6 acceptance run.
- Failure injection is V6-only and occurs before the failed shard performs formal computation.
- Final acceptance requires exactly one recovered shard: index 4.
- No fallback to local compute or to the failed primary provider is allowed.

---

### Task 1: Recovery plan with reserved fallback budget

**Files:**
- Create: `experiments/zero_cost_compute_v0/build_recovery_plan.py`
- Test: `experiments/zero_cost_compute_v0/tests/test_recovery_plan.py`

**Interfaces:**
- Produces: `build_recovery_plan(n, target_items_per_chunk, max_chunks, compiler, providers) -> dict`
- Plan fields used later: `n`, `chunks`, `assignments`, `failure_index`, `repair_provider_id`, `repair_budgets`, `compiler`.

- [ ] Write tests asserting `n=800000` produces 8 primary assignments, every primary assignment is `github-actions-public`, failure index is 4, and `wandbox-public` retains budget 1.
- [ ] Run the full unit suite through the V6 workflow and verify the new tests fail because the module does not exist.
- [ ] Implement the minimal recovery-plan builder with zero-cost/authorized/healthy provider checks and exact reserved budget semantics.
- [ ] Re-run the full unit suite and require all tests to pass.

### Task 2: Multi-provider missing-shard repair planner

**Files:**
- Create: `experiments/zero_cost_compute_v0/pool_repair.py`
- Test: `experiments/zero_cost_compute_v0/tests/test_pool_repair.py`

**Interfaces:**
- Consumes: recovery plan JSON plus primary result directory.
- Produces: `build_repair_plan(plan: dict, primary_results: list[dict]) -> dict` with `repair_assignments`, `repair_indexes`, and provider budget evidence.

- [ ] Write tests for seven valid GitHub primaries with missing index 4, identity mismatch, duplicate primary, wrong sum, and no legal fallback budget.
- [ ] Run tests and verify failure because `pool_repair` does not exist.
- [ ] Implement strict primary validation using `partition_range` and `sum_squares_formula`; emit only missing/invalid indexes and select a different eligible provider with remaining reserved budget.
- [ ] Require the controlled case to emit exactly `[{"index":4,"original_provider_id":"github-actions-public","provider_id":"wandbox-public"}]`.
- [ ] Re-run all unit tests.

### Task 3: Repair executor with explicit provenance

**Files:**
- Create: `experiments/zero_cost_compute_v0/repair_chunk.py`
- Test: `experiments/zero_cost_compute_v0/tests/test_repair_chunk.py`

**Interfaces:**
- Produces: `execute_repair(...) -> dict` containing `attempt="repair"`, `provider_id`, `scheduled_provider_id`, and `original_provider_id`.

- [ ] Write tests proving the executor rejects repair on the original provider, rejects returned provider identity mismatch, and annotates a valid Wandbox repair result.
- [ ] Run tests red.
- [ ] Implement by reusing `wandbox_compute_result` / provider-specific executors; do not duplicate remote execution code.
- [ ] Re-run all unit tests green.

### Task 4: Final recovery verifier

**Files:**
- Create: `experiments/zero_cost_compute_v0/verify_recovery.py`
- Test: `experiments/zero_cost_compute_v0/tests/test_verify_recovery.py`

**Interfaces:**
- Consumes: recovery plan, repair plan, result files, aggregate verification JSON.
- Produces: recovery evidence JSON with status, recovered index, primary/repair counts, provider identities, and local formal compute percentage.

- [ ] Write tests requiring exactly seven valid GitHub primaries, one Wandbox repair at index 4, no repair for other indexes, final aggregate PASS, equal combined/expected sums, and local formal compute 0%.
- [ ] Add negative tests for duplicate repair, wrong recovery index, same-provider repair, and missing current-run provider evidence.
- [ ] Run tests red, implement minimal verifier, then run all tests green.

### Task 5: Real V6 workflow and fault-injection acceptance

**Files:**
- Create: `.github/workflows/zero-cost-compute-v6.yml`

**Interfaces:**
- `tests -> plan -> primary-workers -> repair-plan -> repair-workers -> aggregate`.

- [ ] Add push trigger only for `experiment/zero-cost-compute-v6-self-healing` and `main`, plus manual dispatch.
- [ ] `plan` writes the recovery plan and matrix outputs.
- [ ] `primary-workers` runs all 8 GitHub shards; index 4 intentionally exits before formal compute, with expected failure recorded and no result artifact uploaded. Other shard failures remain fatal.
- [ ] `repair-plan` downloads the seven valid primary artifacts and emits exactly one repair assignment.
- [ ] `repair-workers` executes only index 4 on Wandbox and uploads one repair artifact.
- [ ] `aggregate` downloads seven primary plus one repair result, runs `aggregate_results.py`, then `verify_recovery.py`, and uploads `zero-cost-compute-v6-evidence`.
- [ ] Acceptance assertions: 8 workers total, 7 primary, 1 repair, recovered indexes `[4]`, providers `github-actions-public` and `wandbox-public`, combined sum equals expected sum, local formal compute 0%.

### Task 6: Branch review, main merge, and fresh main verification

**Files:**
- No new implementation files unless review finds a defect.

- [ ] Run a complete branch acceptance workflow after all code-review fixes.
- [ ] Compare branch to `main`; require zero behind commits and no unintended V1-V5 modifications.
- [ ] Open a pull request with exact run IDs and scope boundaries.
- [ ] Fast-forward `main` without force only if the branch is still strictly ahead.
- [ ] Require a fresh `main` V6 workflow run with all jobs successful.
- [ ] Create and close a permanent GitHub issue containing main commit, fresh run ID, artifact ID, exact recovery evidence, and explicit remaining scope boundaries.
