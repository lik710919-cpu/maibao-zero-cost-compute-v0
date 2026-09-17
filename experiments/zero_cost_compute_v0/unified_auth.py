from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from authorization_core import AuthorizationCore, AuthorizationRecord, AuthorizationState
from authorization_ingress import AuthorizationIngressGuard
from authorization_storage import JsonAuthorizationRegistry, WindowsCredentialVault
from capability_activator import CapabilityActivator
from gitlab_auth_adapter import GitLabAuthAdapter


@dataclass(frozen=True)
class ProviderRegistration:
    provider_id: str
    adapter: Any
    authorization_required: bool
    supports_persistent_authorization: bool | None


class UnifiedAuthorizationService:
    """Single mandatory authorization entry point for all eligible platforms."""

    def __init__(
        self,
        *,
        registrations: dict[str, ProviderRegistration],
        vault: Any,
        registry: Any,
        activation_probes: dict[str, Any] | None = None,
    ) -> None:
        self.registrations = dict(registrations)
        self.vault = vault
        self.registry = registry
        self.guard = AuthorizationIngressGuard(registry=registry)

        adapters = {}
        persistent_authorization = {}
        for provider_id, registration in self.registrations.items():
            if provider_id != registration.provider_id:
                raise ValueError("provider registration key does not match provider_id")
            if getattr(registration.adapter, "provider_id", None) != provider_id:
                raise ValueError("provider adapter id does not match registration")
            self.guard.assert_adapter_registration_allowed(
                provider_id=provider_id,
                supports_persistent_authorization=registration.supports_persistent_authorization,
                authorization_required=registration.authorization_required,
                registered_with_unified_core=True,
            )
            adapters[provider_id] = registration.adapter
            persistent_authorization[provider_id] = bool(registration.supports_persistent_authorization)

        self.core = AuthorizationCore(adapters=adapters, vault=vault, registry=registry)
        self.activator = CapabilityActivator(
            core=self.core,
            registry=registry,
            probes=dict(activation_probes or {}),
            ingress_guard=self.guard,
            persistent_authorization=persistent_authorization,
        )

    def _registration(self, provider_id: str) -> ProviderRegistration:
        try:
            return self.registrations[provider_id]
        except KeyError as exc:
            raise KeyError(f"provider is not registered in unified authorization center: {provider_id}") from exc

    def _assert_unified_route(self, provider_id: str) -> ProviderRegistration:
        registration = self._registration(provider_id)
        self.guard.assert_route_allowed(
            provider_id=provider_id,
            supports_persistent_authorization=registration.supports_persistent_authorization,
            authorization_required=registration.authorization_required,
            requested_route="unified",
        )
        return registration

    def begin(self, provider_id: str) -> AuthorizationRecord:
        self._assert_unified_route(provider_id)
        current = self.core.status(provider_id)

        if current is not None and not current.revoked_by_user:
            if current.state in {
                AuthorizationState.AUTHORIZED,
                AuthorizationState.DEGRADED,
                AuthorizationState.REFRESHING,
            }:
                return self.ensure(provider_id)
            if current.state == AuthorizationState.AUTHORIZING:
                polled = self.core.poll(provider_id)
                if polled.state == AuthorizationState.AUTHORIZED:
                    return self.ensure(provider_id)
                return polled

        self.core.begin(provider_id)
        polled = self.core.poll(provider_id)
        if polled.state == AuthorizationState.AUTHORIZED:
            return self.ensure(provider_id)
        return polled

    def status(self, provider_id: str) -> AuthorizationRecord | None:
        self._registration(provider_id)
        return self.core.status(provider_id)

    def ensure(self, provider_id: str) -> AuthorizationRecord:
        self._assert_unified_route(provider_id)
        return self.core.ensure_usable(provider_id)

    def activate(self, provider_id: str) -> dict[str, Any]:
        self._assert_unified_route(provider_id)
        return self.activator.activate(provider_id)

    def revoke(self, provider_id: str, *, explicit_user_revoke: bool) -> AuthorizationRecord:
        self._registration(provider_id)
        if not explicit_user_revoke:
            raise RuntimeError("explicit user revoke flag is required")
        return self.core.revoke(provider_id)

    def public_status(self, provider_id: str) -> dict[str, Any]:
        record = self.status(provider_id)
        if record is None:
            return {
                "provider_id": provider_id,
                "state": AuthorizationState.UNAUTHORIZED.value,
                "authorized": False,
                "revoked_by_user": False,
                "has_runtime_credential": False,
                "acceptance_complete": False,
            }
        return {
            "provider_id": record.provider_id,
            "state": record.state.value,
            "authorized": record.state == AuthorizationState.AUTHORIZED and not record.revoked_by_user,
            "account_id": record.account_id,
            "scopes": list(record.scopes),
            "bound_resource": record.bound_resource,
            "has_runtime_credential": bool(record.runtime_credential_ref),
            "runtime_credential_id": record.runtime_credential_id,
            "acceptance_complete": record.acceptance_complete,
            "revoked_by_user": record.revoked_by_user,
            "last_error": record.last_error,
        }


def default_state_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            raise RuntimeError("LOCALAPPDATA is required on Windows")
        return Path(base) / "Maibao" / "authorization-center"
    return Path.home() / ".local" / "state" / "maibao" / "authorization-center"


def build_default_service(*, state_dir: str | Path | None = None) -> UnifiedAuthorizationService:
    if os.name != "nt":
        raise RuntimeError("production unified authorization V1 currently requires Windows Credential Manager")
    root = Path(state_dir) if state_dir is not None else default_state_dir()
    registry = JsonAuthorizationRegistry(root / "authorization-registry.json")
    vault = WindowsCredentialVault(prefix="maibao-auth")
    gitlab = GitLabAuthAdapter()
    return UnifiedAuthorizationService(
        registrations={
            "gitlab": ProviderRegistration(
                provider_id="gitlab",
                adapter=gitlab,
                authorization_required=True,
                supports_persistent_authorization=True,
            )
        },
        vault=vault,
        registry=registry,
    )


def _json_print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Maibao unified authorization center")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("begin", "status", "ensure"):
        command = subparsers.add_parser(name)
        command.add_argument("--provider", required=True)

    revoke = subparsers.add_parser("revoke")
    revoke.add_argument("--provider", required=True)
    revoke.add_argument("--explicit-user-revoke", action="store_true")

    args = parser.parse_args(argv)
    service = build_default_service()

    if args.command == "begin":
        service.begin(args.provider)
        _json_print(service.public_status(args.provider))
        return 0
    if args.command == "status":
        _json_print(service.public_status(args.provider))
        return 0
    if args.command == "ensure":
        service.ensure(args.provider)
        _json_print(service.public_status(args.provider))
        return 0
    if args.command == "revoke":
        service.revoke(args.provider, explicit_user_revoke=args.explicit_user_revoke)
        _json_print(service.public_status(args.provider))
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
