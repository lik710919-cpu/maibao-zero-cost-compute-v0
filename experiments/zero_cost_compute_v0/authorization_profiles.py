from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AuthorizationProfile:
    resource_provider_id: str
    authorization_provider_id: str
    authorization_required: bool
    supports_persistent_authorization: bool | None


_PROFILES = {
    "gitlab-hosted-runners": AuthorizationProfile(
        resource_provider_id="gitlab-hosted-runners",
        authorization_provider_id="gitlab",
        authorization_required=True,
        supports_persistent_authorization=True,
    ),
}


def profile_for_candidate(record: dict[str, Any]) -> AuthorizationProfile:
    provider_id = str(record["provider_id"])
    known = _PROFILES.get(provider_id)
    if known is not None:
        return known
    return AuthorizationProfile(
        resource_provider_id=provider_id,
        authorization_provider_id=str(record.get("authorization_provider_id") or provider_id),
        authorization_required=bool(record.get("authorization_required", True)),
        supports_persistent_authorization=record.get("supports_persistent_authorization"),
    )


def apply_profile(record: dict[str, Any]) -> dict[str, Any]:
    profile = profile_for_candidate(record)
    merged = dict(record)
    merged["authorization_provider_id"] = profile.authorization_provider_id
    merged["authorization_required"] = profile.authorization_required
    merged["supports_persistent_authorization"] = profile.supports_persistent_authorization
    return merged
