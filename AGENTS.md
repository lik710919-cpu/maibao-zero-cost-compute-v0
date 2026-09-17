# MaiBao Engineering Start Gate

This repository is governed by the canonical MaiBao Fast Path start gate.

## Mandatory pre-construction gate

For every new engineering task, before creating or editing any design, plan, test, implementation, configuration, workflow, or documentation file for that task:

1. A branch-bound start receipt MUST exist at `.maibao/fast-path-start.json`.
2. The receipt MUST use schema `MAIBAO_FAST_PATH_START_GATE_V1` and MUST match this repository and the current branch.
3. The receipt MUST be produced from the canonical authority `lik710919-cpu/maibao-reserve-repo` at `feat/fast-path-machine-start-gate-20260917`.
4. The receipt MUST pass `.maibao/verify-fast-path-start-gate.py` before substantive construction begins.
5. `NON_FAST_PATH` is a valid classification but does NOT bypass the start gate.
6. If the receipt is missing, invalid, stale, copied from another branch, outside owned paths, or bound to a different authority, FAIL CLOSED: do not proceed with planning, TDD, implementation, configuration, workflow changes, documentation changes, commit, push, or merge for the task.
7. Hard R5 / Provider / Stable Core authority boundaries remain non-overridable.

Before a valid start receipt exists, the only permitted task mutation is the minimum change needed to obtain or install the valid start receipt and its gate metadata.

## Branch discipline

1. Engineering construction MUST occur on a task or specialty branch. Direct engineering writes to `main` are forbidden.
2. Merge or promotion to `main` is permitted only after the branch-bound start receipt validates and the `Fast Path Start Gate` check has completed successfully when that remote check is available for the repository.
3. A missing, cancelled, unavailable, or unstarted gate runner is NOT a bypass. Treat it as FAIL CLOSED and do not merge or promote until the required gate evidence is available.
4. The only bootstrap exception is the minimum one-time mutation required to install or repair the start-gate control itself; that exception must be recorded in authority evidence and may not carry unrelated engineering changes.

## Catch-up rule

`catch_up_audit=true` is allowed only for work that demonstrably started before the machine start gate was activated for this repository. New work that starts after activation MUST use a normal pre-construction start receipt and MUST NOT use catch-up registration.

## Completion

The start gate does not replace existing engineering closure. TDD, impact regression, commit/push, remote readback, evidence, closeout, and all production preconditions remain mandatory under the existing governance.
