from __future__ import annotations

from dataclasses import dataclass
from typing import Any


PROVIDER_ID = "huggingface-inference-providers"
DEFAULT_BASE_URL = "https://router.huggingface.co/v1"
CAPABILITY_SCOPE = "MAIBAO_SHARED"
CAPABILITY_KIND = "ai_inference"


@dataclass(frozen=True)
class InferenceRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: dict[str, Any]

    def safe_summary(self) -> dict[str, Any]:
        authorization = self.headers.get("Authorization", "")
        safe_headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() != "authorization"
        }
        return {
            "method": self.method,
            "url": self.url,
            "headers": safe_headers,
            "body": self.body,
            "token_present": authorization.startswith("Bearer ") and len(authorization) > 7,
        }


def _required_text(value: str, field: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field} is required")
    if "\n" in text or "\r" in text:
        raise ValueError(f"{field} contains an invalid newline")
    return text


def build_chat_completion_request(
    *,
    token: str,
    model: str,
    prompt: str,
    base_url: str = DEFAULT_BASE_URL,
) -> InferenceRequest:
    clean_token = _required_text(token, "token")
    clean_model = _required_text(model, "model")
    clean_prompt = str(prompt).strip()
    if not clean_prompt:
        raise ValueError("prompt is required")
    clean_base = str(base_url).rstrip("/")
    if clean_base != DEFAULT_BASE_URL:
        raise ValueError("unsupported Hugging Face router base URL")
    return InferenceRequest(
        method="POST",
        url=f"{clean_base}/chat/completions",
        headers={
            "Authorization": f"Bearer {clean_token}",
            "Content-Type": "application/json",
        },
        body={
            "model": clean_model,
            "messages": [{"role": "user", "content": clean_prompt}],
        },
    )


def parse_chat_completion_response(response: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise ValueError("response must be an object")
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("response has no choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise ValueError("response choice is invalid")
    message = first.get("message")
    if not isinstance(message, dict):
        raise ValueError("response choice has no message")
    text = message.get("content")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("response message has no text")
    return {
        "response_id": str(response.get("id", "")).strip(),
        "text": text.strip(),
    }


def build_verified_evidence(
    *,
    response: dict[str, Any],
    expected_text: str,
    model: str,
    free_tier_confirmed: bool,
) -> dict[str, Any]:
    parsed = parse_chat_completion_response(response)
    expected = str(expected_text).strip()
    if not expected or parsed["text"] != expected:
        raise ValueError("Hugging Face inference challenge mismatch")
    response_id = parsed["response_id"] or "response-without-id"
    return {
        "provider_id": PROVIDER_ID,
        "provider_evidence": f"real:huggingface:{response_id}",
        "model": _required_text(model, "model"),
        "verified": True,
        "healthy": True,
        "zero_cash_cost": bool(free_tier_confirmed),
        "local_compute_used": False,
        "capability_scope": CAPABILITY_SCOPE,
        "capability_kind": CAPABILITY_KIND,
        "generic_compute": False,
        "text": parsed["text"],
    }
