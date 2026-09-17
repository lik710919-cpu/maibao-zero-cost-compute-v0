# Zero-Cash-Cost External Compute V2 Multi-Provider Control Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and externally validate a provider-agnostic zero-cash-cost compute control plane that truthfully distinguishes live providers from unavailable or unauthorized candidates.

**Architecture:** Add focused Python modules for provider snapshots, eligibility/ranking, and catalog evidence. GitHub-hosted compute remains the only live provider until a second real provider is authorized and successfully probed. The V2 workflow validates the control plane externally and emits permanent evidence without claiming a second live provider.

**Tech Stack:** Python 3 standard library, GitHub Actions, JSON evidence artifacts.

**Spec:** `docs/superpowers/specs/2026-09-17-zero-cost-compute-v2-multipool-design.md`

## Global Constraints
- Local formal compute contribution is 0%.
- Only legal, authorized, provably zero-incremental-cash-cost providers may be eligible.
- No synthetic provider may count toward live provider count.
- Routing must fail closed when no eligible provider exists.

---

### Task 1: RED tests for provider eligibility and routing
**Files:**
- Create: `experiments/zero_cost_compute_v0/tests/test_provider_routing.py`

**Interfaces:**
- Consumes: future `ProviderSnapshot`, `eligible_providers`, `route_provider`.
- Produces: executable behavior contract.

- [ ] Write tests for paid/unknown rejection, unauthorized rejection, queue ranking, capacity tiebreak, fallback order, and fail-closed behavior.
- [ ] Run the external V0 test workflow on the branch and verify RED because the modules do not exist.

### Task 2: Implement provider model and router
**Files:**
- Create: `experiments/zero_cost_compute_v0/provider_model.py`
- Create: `experiments/zero_cost_compute_v0/provider_router.py`

**Interfaces:**
- Produces: `ProviderSnapshot`, `eligible_providers(list)`, `route_provider(list)`.

- [ ] Implement only the behavior required by the RED tests.
- [ ] Run the full external unit suite and verify GREEN.

### Task 3: Build truthful provider catalog evidence
**Files:**
- Create: `experiments/zero_cost_compute_v0/provider_catalog.py`
- Create: `experiments/zero_cost_compute_v0/tests/test_provider_catalog.py`

**Interfaces:**
- Produces: catalog JSON with `live_provider_count`, `local_formal_compute_percent`, statuses, and route decision.

- [ ] RED test: only real ready providers count as live; unavailable candidates do not.
- [ ] Implement catalog creation and evidence validation.
- [ ] Verify GREEN externally.

### Task 4: External V2 acceptance workflow
**Files:**
- Create: `.github/workflows/zero-cost-compute-v2.yml`

**Interfaces:**
- Runs tests and catalog generation on GitHub-hosted external runners.
- Emits `zero-cost-compute-v2-control-plane-evidence` artifact.

- [ ] Run on feature branch.
- [ ] Verify overall workflow success, local formal compute 0%, GitHub provider ready, live provider count truthful, and no fake cross-provider success.

### Task 5: Integrate and main-branch reverify
**Files:**
- Modify: `README.md`

- [ ] Document V2 status and the exact remaining gate for a real second provider.
- [ ] Open PR and merge after fresh feature-branch verification.
- [ ] Run V2 from main and record permanent acceptance evidence.
