from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

from huggingface_provider import (
    build_chat_completion_request,
    build_verified_evidence,
)


def perform_request(request, *, timeout_seconds: float = 30.0) -> dict:
    wire = json.dumps(request.body).encode("utf-8")
    http_request = Request(
        request.url,
        data=wire,
        headers=request.headers,
        method=request.method,
    )
    with urlopen(http_request, timeout=timeout_seconds) as response:
        payload = response.read().decode("utf-8")
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise RuntimeError("Hugging Face returned a non-object response")
    return parsed


def activate(
    *,
    model: str,
    prompt: str,
    expected_text: str,
    confirm_free_tier: bool,
    requester=perform_request,
    token_cache_getter=None,
) -> dict:
    if confirm_free_tier is not True:
        raise RuntimeError("free-tier confirmation is required before live activation")

    request = build_chat_completion_request(
        model=model,
        prompt=prompt,
        token_cache_getter=token_cache_getter,
    )
    response = requester(request)
    evidence = build_verified_evidence(
        response=response,
        expected_text=expected_text,
        model=model,
        free_tier_confirmed=True,
    )
    return {
        **evidence,
        "activation_state": "READY",
        "auth_mode": "huggingface_browser_device_oauth",
        "token_source": "huggingface_hub_standard_cache",
        "manual_token_paste_used": False,
        "free_tier_guard": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Activate MaiBao Hugging Face shared inference capability"
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt", default="Return exactly READY")
    parser.add_argument("--expected-text", default="READY")
    parser.add_argument("--confirm-free-tier", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    evidence = activate(
        model=args.model,
        prompt=args.prompt,
        expected_text=args.expected_text,
        confirm_free_tier=args.confirm_free_tier,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "provider_id": evidence["provider_id"],
                "activation_state": evidence["activation_state"],
                "verified": evidence["verified"],
                "model": evidence["model"],
                "free_tier_guard": evidence["free_tier_guard"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
