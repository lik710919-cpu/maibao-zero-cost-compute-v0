from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from authorization_core import AuthorizationState


class CapabilityActivator:
    def __init__(
        self,
        *,
        core: Any,
        registry: Any,
        probes: dict[str, Callable[[Any], dict[str, Any]]],
        ingress_guard: Any | None = None,
        persistent_authorization: dict[str, bool] | None = None,
    ) -> None:
        self.core = core
        self.registry = registry
        self.probes = dict(probes)
        self.ingress_guard = ingress_guard
        self.persistent_authorization = dict(persistent_authorization or {})

    def activate(self, provider_id: str) -> dict[str, Any]:
        if self.ingress_guard is not None:
            self.ingress_guard.assert_activation_allowed(
                provider_id=provider_id,
                supports_persistent_authorization=self.persistent_authorization.get(provider_id, True),
            )

        record = self.core.ensure_usable(provider_id)
        if record.state != AuthorizationState.AUTHORIZED or record.revoked_by_user:
            raise RuntimeError("provider is not authorized for activation")

        try:
            probe = self.probes[provider_id]
        except KeyError as exc:
            raise KeyError(f"no activation probe registered for provider: {provider_id}") from exc

        try:
            evidence = probe(record)
        except Exception:
            failed = replace(
                record,
                acceptance_complete=False,
                last_error="activation_probe_failed",
            )
            self.registry.put(failed)
            raise

        if evidence.get("verified") is not True:
            failed = replace(
                record,
                acceptance_complete=False,
                last_error="activation_evidence_not_verified",
            )
            self.registry.put(failed)
            raise RuntimeError("activation evidence was not verified")
        if evidence.get("local_compute_used") is not False:
            failed = replace(
                record,
                acceptance_complete=False,
                last_error="local_formal_compute_detected",
            )
            self.registry.put(failed)
            raise RuntimeError("local compute cannot activate a formal external provider")

        active = replace(
            record,
            acceptance_complete=True,
            last_error=None,
        )
        self.registry.put(active)
        return {
            **evidence,
            "provider_id": evidence.get("provider_id", provider_id),
            "live_active": True,
            "authorization_state": active.state.value,
        }
