# V7 Resource Growth Design

## Goal
Turn resource research into an immediately usable growth capability for the zero-cash-cost distributed compute pool.

V7 does not directly claim new external compute capacity. It creates the qualification gate that decides which researched providers are safe to activate, which require manual authorization, and which must stay research-only.

## Frozen constraints
- Formal compute remains external; local compute is control-only.
- New cash compute cost must remain zero.
- Provider usage must be authorized and within platform rules.
- Existing V6 cross-provider self-healing remains intact.
- Research output must become machine-readable and feed the next activation step.

## Architecture

### Provider candidate record
Each researched source is represented by a machine-readable record with:
- provider_id
- display_name
- source_type
- evidence_url
- evidence_date
- zero_cash_allowance
- hard_quota_stop
- requires_billing_account
- automatic_overage_possible
- authorized_use_confirmed
- compute_class
- quota_summary
- activation_mode
- notes

### Qualification engine
The engine classifies every candidate into one of four states:
- `auto_eligible`: zero-cash allowance exists, overage is fail-closed, use is authorized, and no billing exposure is required.
- `manual_gate`: useful zero-cost allowance exists but activation requires credentials, billing-account setup, grant approval, or other user-controlled authorization.
- `control_only`: free resource exists but execution limits make it unsuitable for formal compute; it may still serve control-plane work.
- `research_only`: evidence or authorization is insufficient, or cost exposure cannot be bounded safely.

The engine must fail closed. Missing cost, authorization, or overage data cannot produce `auto_eligible`.

### Seed research set
V7 seeds the registry with evidence-backed candidates researched on 2026-09-17:
- GitLab hosted runners: free namespace quota, quota-enforced.
- Modal Starter: monthly included compute, but metered usage can continue beyond included credits.
- Google Cloud Run: monthly free tier, but billing-backed usage can exceed the free tier.
- Cloudflare Workers Free: hard free-plan limits, but CPU-per-request is too small for formal pool computation.
- Kaggle Notebooks: free accelerators exist, but automated production-style dispatch requires a separate terms/automation qualification before activation.

## Activation policy
`auto_eligible` is not the same as already active. It means the provider is safe to move into an adapter/probe implementation without reopening cost policy. Actual activation still requires a live execution proof.

V7 itself is activated when:
1. the registry is machine-readable,
2. qualification tests pass,
3. the workflow produces an evidence artifact listing activation-ready and gated candidates,
4. the full V1-V6 regression suite remains green.

## Next-use rule
The first `auto_eligible` provider becomes the next adapter target. `manual_gate` candidates are retained with explicit blockers so they can be activated immediately when authorization becomes available.
