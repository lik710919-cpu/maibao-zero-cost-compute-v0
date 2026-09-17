# V8 GitLab Provider Adapter Implementation Plan

## Objective
Produce an adapter-ready GitLab provider path under the zero-cash-cost and authorization constraints, then stop only at the external-credential boundary if no authorized GitLab runtime is available.

## Task 1: Define adapter contracts with failing tests
Add tests first for:
- conservative free-minute budget calculation,
- dispatch rejection when budget state is missing or unsafe,
- trigger request construction without leaking secrets,
- pipeline polling terminal-state interpretation,
- result artifact identity/nonce/bounds validation,
- dry-run evidence showing local formal compute remains zero.

Run the full suite and verify the new tests fail because the adapter does not yet exist.

## Task 2: Implement budget guard and request builder
Add the minimum GitLab adapter model and pure functions required by the tests. No network side effects in this task.

## Task 3: Implement worker contract
Add a portable GitLab worker script and `.gitlab-ci.yml` template under the experiment directory. The worker accepts only bounded shard inputs, computes the existing deterministic formal workload, and writes a JSON result artifact with provider/pipeline/job evidence.

## Task 4: Implement controller network path
Add a controller capable of:
- trigger pipeline,
- poll exact pipeline,
- list exact pipeline jobs,
- download exact result artifact,
- normalize and verify the result.

Credentials must come only from runtime environment variables and must never be written to logs or artifacts.

## Task 5: Add adapter-ready acceptance workflow
On GitHub, run:
- the full existing regression suite,
- V8 tests,
- a credential-free dry-run that produces the exact dispatch plan and verifies the budget guard.

Upload V8 adapter-readiness evidence.

## Task 6: Live activation gate
If authorized GitLab credentials/project are available, execute a bounded live shard and retain evidence.
If they are not available, mark only the live activation gate as blocked; do not block completion of the adapter-ready engineering work.

## Completion criteria
Stage A is complete when all code/tests/dry-run evidence are green and merged.
Stage B is complete only after a real GitLab-hosted runner executes a formal shard and the returned artifact passes identity and result verification.
