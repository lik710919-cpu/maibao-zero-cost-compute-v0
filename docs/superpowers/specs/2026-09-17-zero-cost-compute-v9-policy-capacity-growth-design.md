# V9 Policy-Aware Capacity Growth Design

## Goal
Expand the resource-growth system so large advertised free quotas cannot be mistaken for formally usable pool capacity before cost safety, authorization, and acceptable-use scope are all proven.

V9 builds on V7 qualification and V8 adapter readiness. It does not activate any new provider by itself. It improves the growth engine so research can safely prioritize the next engineering target.

## Frozen constraints
- Formal compute remains external; local compute is control-only.
- New cash compute cost remains zero.
- Provider use must be authorized and within platform terms.
- No fake accounts, quota evasion, billing bypass, or excessive automated activity.
- Advertised capacity is never counted as active capacity before live evidence.

## New candidate policy dimensions
Every candidate adds:
- `terms_scope`: `general_compute`, `project_ci_only`, `developer_environment`, `control_only`, or `unconfirmed`.
- `terms_scope_confirmed`: whether current official policy clearly covers the proposed use.
- `external_authorization_required`: whether account/project approval is still needed.
- `advertised_monthly_capacity_minutes`: normalized research estimate when meaningful, otherwise null.
- `advertised_monthly_core_hours`: normalized core-hour estimate when meaningful, otherwise null.
- `max_concurrency`: documented concurrency when known.
- `capacity_visibility`: `visible`, `not_visible`, or `unknown`.
- `formal_pool_eligible`: whether the policy scope can support general formal shard compute after live activation.

## Qualification semantics
The existing cost/authorization states remain, but policy scope becomes an independent gate.

A candidate can become `auto_eligible` only if all of the following hold:
1. a zero-cash allowance exists;
2. cost exposure is fail-closed;
3. authorization is confirmed;
4. terms scope is confirmed;
5. the terms scope permits the intended formal workload;
6. the compute class is formal.

If free capacity is large but terms scope is limited to project CI, developer environments, or remains unconfirmed, the candidate is not counted as general formal pool capacity. It is classified into an explicit policy gate and can still be used for project-native testing/development if permitted.

## Seed expansion
V9 adds current evidence-backed candidates:

### CircleCI open-source Free plan
- Up to 400,000 free credits/month for Linux open-source builds, described as roughly 80,000 build minutes.
- Free open-source credit visibility is not exposed in the web application.
- Acceptable Use Policy prohibits service-bureau/third-party use except as permitted and excessive automated bulk activity.
- Classification: `policy_gate` for general formal compute; high-priority candidate for project-native CI validation workloads.

### GitHub Codespaces personal free quota
- GitHub Free personal accounts include 120 core-hours/month and 15 GB-month storage.
- Without a valid payment method, use is blocked when included quota is exhausted.
- GitHub describes the included use as intended for open-source contributions or side projects.
- Classification: `developer_environment`; useful for development/test capacity but not general automated pool capacity without a clearer use-scope basis.

### Bitbucket Pipelines Free
- 50 build minutes/month, up to 10 concurrent steps.
- Free plan does not include overage protection.
- Classification: `manual_gate` / low priority because safety and capacity are both weak relative to alternatives.

### Azure DevOps Pipelines private free grant
- 1 parallel job, up to 60 minutes/job, 1,800 minutes/month.
- Free grant requires linking a valid Azure subscription and setting up billing.
- Classification: `manual_gate`.

## Priority model
Research priority is not raw quota size.

Priority considers, in order:
1. terms-scope safety;
2. hard zero-cash enforcement;
3. authorization friction;
4. useful capacity;
5. integration simplicity;
6. evidence visibility.

A large quota behind an unresolved policy gate ranks below a smaller resource that is clearly authorized and fail-closed.

## Evidence output
The growth report adds:
- `active_capacity_claimed`: always false for research candidates;
- `formal_pool_candidates`;
- `project_native_candidates`;
- `developer_environment_candidates`;
- `policy_gate_candidates`;
- `manual_gate_candidates`;
- a prioritized `next_research_target` and `next_adapter_target` chosen only from policy-safe candidates.

## Activation rule
V9 is activated when the expanded tests and full regression suite pass, a machine-readable evidence artifact is generated, and no candidate with unresolved terms scope is promoted to formal pool capacity.
