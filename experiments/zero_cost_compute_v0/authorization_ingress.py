from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from authorization_core import AuthorizationState


class AuthorizationRoute(str, Enum):
    UNIFIED_REQUIRED = "UNIFIED_REQUIRED"
    EXCEPTION_ALLOWED = "EXCEPTION_ALLOWED"
    NOT_REQUIRED = "NOT_REQUIRED"


@dataclass(frozen=True)
class AuthorizationIngressDecision:
    provider_id: str
    route: AuthorizationRoute
    intercept: bool
    reason: str


class AuthorizationIngressGuard:
    """Mandatory gateway for provider authorization and activation.

    Any provider that both requires authorization and supports a persistent
    one-time user authorization relationship must use the unified
    authorization core. Private/parallel authorization paths are rejected.
    """

    def __init__(self, registry: Any | None = None) -> None:
        self.registry = registry

    def classify(
        self,
        *,
        provider_id: str,
        supports_persistent_authorization: bool,
        authorization_required: bool,
    ) -> AuthorizationIngressDecision:
        if not provider_id:
            raise ValueError("provider id is required")
        if not authorization_required:
            return AuthorizationIngressDecision(
                provider_id=provider_id,
                route=AuthorizationRoute.NOT_REQUIRED,
                intercept=False,
                reason="provider_does_not_require_authorization",
            )
        if supports_persistent_authorization:
            return AuthorizationIngressDecision(
                provider_id=provider_id,
                route=AuthorizationRoute.UNIFIED_REQUIRED,
                intercept=True,
                reason="persistent_authorization_must_use_unified_center",
            )
        return AuthorizationIngressDecision(
            provider_id=provider_id,
            route=AuthorizationRoute.EXCEPTION_ALLOWED,
            intercept=False,
            reason="provider_has_no_persistent_authorization_mechanism",
        )

    def assert_route_allowed(
        self,
        *,
        provider_id: str,
        supports_persistent_authorization: bool,
        authorization_required: bool,
        requested_route: str,
    ) -> AuthorizationIngressDecision:
        decision = self.classify(
            provider_id=provider_id,
            supports_persistent_authorization=supports_persistent_authorization,
            authorization_required=authorization_required,
        )
        normalized = (requested_route or "").strip().lower()
        if decision.route == AuthorizationRoute.UNIFIED_REQUIRED and normalized not in {
            "unified",
            "unified_authorization",
            "unified_auth_center",
        }:
            raise RuntimeError(
                f"{provider_id} supports persistent authorization and must enter through the unified authorization center"
            )
        return decision

    def assert_adapter_registration_allowed(
        self,
        *,
        provider_id: str,
        supports_persistent_authorization: bool,
        authorization_required: bool,
        registered_with_unified_core: bool,
    ) -> AuthorizationIngressDecision:
        decision = self.classify(
            provider_id=provider_id,
            supports_persistent_authorization=supports_persistent_authorization,
            authorization_required=authorization_required,
        )
        if decision.route == AuthorizationRoute.UNIFIED_REQUIRED and not registered_with_unified_core:
            raise RuntimeError(
                f"{provider_id} cannot register a private authorization adapter outside AuthorizationCore"
            )
        return decision

    def assert_activation_allowed(
        self,
        *,
        provider_id: str,
        supports_persistent_authorization: bool,
    ):
        if not supports_persistent_authorization:
            return None
        if self.registry is None:
            raise RuntimeError("unified authorization registry is required before activation")
        record = self.registry.get(provider_id)
        if record is None:
            raise RuntimeError("provider has not entered the unified authorization center")
        if record.state != AuthorizationState.AUTHORIZED or record.revoked_by_user:
            raise RuntimeError(
                f"provider authorization state {record.state.value} is not allowed to activate"
            )
        return record


def authorization_policy_from_candidate(record: dict[str, Any]) -> AuthorizationIngressDecision:
    """Convert provider discovery metadata into the mandatory auth route.

    Discovery/onboarding code calls this before any provider-specific
    authorization implementation is selected.
    """

    guard = AuthorizationIngressGuard()
    return guard.classify(
        provider_id=str(record["provider_id"]),
        supports_persistent_authorization=bool(
            record.get("supports_persistent_authorization", False)
        ),
        authorization_required=bool(record.get("authorization_required", False)),
    )
