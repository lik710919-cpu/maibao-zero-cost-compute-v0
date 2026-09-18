# Hugging Face browser-auth activation evidence

Date: 2026-09-18
Repository: lik710919-cpu/maibao-zero-cost-compute-v0
Branch: feat/huggingface-browser-auth-20260918

## Goal

Reuse Hugging Face official browser/device OAuth and the standard huggingface_hub token cache.
No access token is pasted into ChatGPT and no parallel private auth path is introduced.

## Official behavior verified

- `hf auth login` supports browser/device login.
- The resulting access token is persisted in the Hugging Face standard cache.
- `huggingface_hub.get_token()` can retrieve the active cached token for SDK/API use.
- Free users currently receive USD 0.10/month Inference Providers credits.
- Extra use requires purchased credits.

## Engineering changes

- `huggingface_provider.py` now resolves an explicit token first, otherwise the official Hugging Face cached token.
- Missing login fails closed.
- Secret values remain excluded from safe summaries.
- `huggingface_activation.py` is the live activation entry.
- Live activation requires explicit free-tier confirmation before a network request.
- Shared capability manifest now declares browser/device OAuth and standard-cache token source.

## Focused validation

Validated behaviors:
1. Browser-auth cached token is used when no explicit token is supplied.
2. Explicit token wins over cache.
3. Missing cache fails closed.
4. Shared manifest declares official browser-device OAuth.
5. Live activation refuses without free-tier confirmation.
6. Successful verified response produces READY evidence without exposing a token.

Result: 6/6 PASS.

## Live account state

The authorized Windows execution device is currently offline from the remote command channel, so the interactive device authorization and real external inference request cannot be performed from this branch session.

Therefore:
- Browser-auth engineering: PASS
- Free-cost guard: PASS
- Shared contract: PASS
- Secret handling: PASS
- Real account authorization: PENDING USER/DEVICE INTERACTIVE APPROVAL
- Real external inference receipt: PENDING
- Production live state remains ADAPTER_READY until those last two runtime facts exist.

No live READY claim is made here.
