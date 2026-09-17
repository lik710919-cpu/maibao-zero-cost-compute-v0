# Zero-Cash-Cost External Compute V2 Multi-Provider Control Plane Design

## Goal
Extend V1 from one compute provider into a provider-agnostic control plane that can discover, rank, select, and fail over among multiple zero-cash-cost external compute providers without counting local compute.

## Frozen constraints
- Local machine remains ignition/control only; local formal compute contribution is 0%.
- Providers must be legal, authorized, and expected to incur zero incremental cash compute cost.
- No provider may be reported as live unless a real external execution on that provider is observed.
- A missing second provider must be reported honestly as `authorization_required` or `unavailable`; synthetic fixtures are allowed only for routing tests.

## Architecture
V2 introduces a provider catalog, provider snapshots, a zero-cost eligibility guard, and a router. Each provider snapshot records provider id, authorization state, health, zero-cash-cost eligibility, queue estimate, capacity, and evidence. The router filters ineligible providers, ranks eligible providers, and returns a primary provider plus ordered fallback providers.

The existing GitHub-hosted runner remains the only currently live compute provider. Additional providers are adapters that become live only after real authorization and a successful external probe. The control plane is therefore multi-provider-ready before a second provider is connected, but the project does not claim cross-provider compute closure until a second provider actually executes work.

## Data model
`ProviderSnapshot` fields: `provider_id`, `authorized`, `healthy`, `zero_cash_cost`, `queue_seconds`, `capacity`, `evidence`, `status`.

Statuses are `ready`, `authorization_required`, `unhealthy`, `paid_or_unknown`, or `unavailable`.

## Routing rules
1. Reject any provider that is not authorized, not healthy, or not provably zero-cash-cost.
2. Prefer lower queue time.
3. Prefer greater capacity when queue time is equal.
4. Produce ordered fallbacks for every route decision.
5. If no provider is eligible, fail closed rather than using local compute or an unknown-cost provider.

## Acceptance
- Unit tests prove zero-cost filtering, ranking, fail-closed behavior, and fallback selection.
- A GitHub Actions acceptance workflow runs the tests externally, writes a real provider catalog showing GitHub as `ready`, and writes any unconfigured providers as non-live.
- The acceptance evidence must state `local_formal_compute_percent=0` and `live_provider_count` truthfully.
- Cross-provider closure is a later gate requiring `live_provider_count >= 2` with real execution evidence from two distinct provider ids.
