# Hugging Face shared capability integration evidence

Date: 2026-09-18
Repository: lik710919-cpu/maibao-zero-cost-compute-v0
Branch: feat/huggingface-shared-capability-20260918

## Scope

- One implementation repository only.
- Capability is published as MAIBAO_SHARED for cross-repository consumption.
- Capability kind is ai_inference.
- It is explicitly excluded from generic compute routing.

## External contract

- Router base URL: https://router.huggingface.co/v1
- Authentication: fine-grained Hugging Face token with Inference Providers permission.
- Billing basis verified against Hugging Face Inference Providers pricing documentation on 2026-09-18.
- Free-user monthly Inference Providers credit is currently USD 0.10 and is documented as subject to change.
- Additional usage requires purchased credits, therefore live READY is gated on free-tier confirmation.

## TDD evidence

RED 1:
- Command: python -m unittest tests.test_huggingface_provider
- Result: 3 errors.
- Expected reason: huggingface_provider module did not exist.

GREEN 1:
- Same focused command.
- Result: 3 tests passed.

RED 2:
- Expanded shared-registration contract.
- Result: 3 expected errors: missing shared manifest, missing Hugging Face snapshot, missing candidate catalog entry.

GREEN 2:
- Command: python -m unittest tests.test_huggingface_provider tests.test_provider_catalog tests.test_provider_routing
- Result: 12 tests passed.

Impact regression:
- Command: python -m unittest discover -s tests -p "test_*.py"
- Result: 128 tests passed.

## Live activation truth

Environment probe: HF_TOKEN_MISSING.

Therefore:
- Adapter engineering: PASS.
- Shared capability registration: PASS.
- Generic-compute exclusion: PASS.
- Repository regression: PASS.
- Real external inference proof: NOT YET AVAILABLE.
- Live activation state must remain ADAPTER_READY until an authorized token and a free-tier-safe real inference receipt are available.

No live READY claim is made by this evidence.
