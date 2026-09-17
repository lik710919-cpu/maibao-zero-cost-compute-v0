from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Protocol


class AuthorizationState(str, Enum):
    UNAUTHORIZED = "UNAUTHORIZED"
    AUTHORIZING = "AUTHORIZING"
    AUTHORIZED = "AUTHORIZED"
    REFRESHING = "REFRESHING"
    DEGRADED = "DEGRADED"
    REAUTH_REQUIRED = "REAUTH_REQUIRED"
    REVOKED_BY_USER = "REVOKED_BY_USER"


@dataclass(frozen=True)
class AuthorizationSession:
    provider_id: str
    verification_uri: str | None = None
    user_code: str | None = None
    expires_in: int | None = None


@dataclass(frozen=True)
class AuthorizationRecord:
    provider_id: str
    state: AuthorizationState
    account_id: str | None = None
    scopes: tuple[str, ...] = ()
    user_credential_ref: str | None = None
    runtime_credential_ref: str | None = None
    runtime_credential_id: str | None = None
    revoked_by_user: bool = False
    authorized_at: str | None = None
    last_verified_at: str | None = None
    bound_resource: str | None = None
    acceptance_complete: bool = False
    last_error: str | None = None


class ProviderAuthAdapter(Protocol):
    provider_id: str

    def begin_authorization(self) -> AuthorizationSession: ...
    def poll_authorization(self) -> dict[str, Any]: ...
    def validate_identity(self) -> dict[str, Any]: ...
    def inspect_scopes(self) -> list[str] | tuple[str, ...]: ...
    def refresh_authorization(self) -> dict[str, Any]: ...
    def create_runtime_credentials(self, vault: "CredentialVault") -> dict[str, Any]: ...
    def validate_runtime_credentials(self, runtime_ref: str | None, vault: "CredentialVault") -> bool: ...
    def revoke_runtime_credentials(self, runtime_ref: str | None, vault: "CredentialVault") -> None: ...
    def revoke_user_authorization(self) -> None: ...


class CredentialVault(Protocol):
    def put(self, name: str, secret: str) -> str: ...
    def get(self, ref: str) -> str: ...
    def delete(self, ref: str) -> None: ...
    def exists(self, ref: str) -> bool: ...


class AuthorizationRegistry(Protocol):
    def get(self, provider_id: str) -> AuthorizationRecord | None: ...
    def put(self, record: AuthorizationRecord) -> None: ...


class AuthorizationCore:
    def __init__(
        self,
        *,
        adapters: dict[str, ProviderAuthAdapter],
        vault: CredentialVault,
        registry: AuthorizationRegistry,
    ) -> None:
        self.adapters = dict(adapters)
        self.vault = vault
        self.registry = registry

    def _adapter(self, provider_id: str) -> ProviderAuthAdapter:
        try:
            return self.adapters[provider_id]
        except KeyError as exc:
            raise KeyError(f"unknown authorization provider: {provider_id}") from exc

    def status(self, provider_id: str) -> AuthorizationRecord | None:
        return self.registry.get(provider_id)

    def begin(self, provider_id: str) -> AuthorizationSession:
        adapter = self._adapter(provider_id)
        session = adapter.begin_authorization()
        self.registry.put(
            AuthorizationRecord(
                provider_id=provider_id,
                state=AuthorizationState.AUTHORIZING,
                revoked_by_user=False,
            )
        )
        return session

    def poll(self, provider_id: str) -> AuthorizationRecord:
        adapter = self._adapter(provider_id)
        current = self.registry.get(provider_id)
        if current is not None and current.state == AuthorizationState.REVOKED_BY_USER:
            raise RuntimeError("authorization was explicitly revoked by user")
        result = adapter.poll_authorization()
        if result.get("reauth_required"):
            record = AuthorizationRecord(
                provider_id=provider_id,
                state=AuthorizationState.REAUTH_REQUIRED,
                revoked_by_user=False,
            )
        elif result.get("authorized"):
            record = AuthorizationRecord(
                provider_id=provider_id,
                state=AuthorizationState.AUTHORIZED,
                account_id=str(result.get("account_id")) if result.get("account_id") is not None else None,
                scopes=tuple(str(value) for value in result.get("scopes", ())),
                user_credential_ref=result.get("user_credential_ref"),
                revoked_by_user=False,
            )
        else:
            record = AuthorizationRecord(
                provider_id=provider_id,
                state=AuthorizationState.AUTHORIZING,
                revoked_by_user=False,
            )
        self.registry.put(record)
        return record

    def ensure_usable(self, provider_id: str) -> AuthorizationRecord:
        adapter = self._adapter(provider_id)
        record = self.registry.get(provider_id)
        if record is None:
            raise RuntimeError("provider has not been authorized")
        if record.state == AuthorizationState.REVOKED_BY_USER or record.revoked_by_user:
            raise RuntimeError("authorization was explicitly revoked by user")
        if record.state in {AuthorizationState.UNAUTHORIZED, AuthorizationState.AUTHORIZING}:
            raise RuntimeError("provider authorization is not complete")

        try:
            identity = adapter.validate_identity()
        except Exception:
            degraded = replace(
                record,
                state=AuthorizationState.DEGRADED,
                revoked_by_user=False,
                last_error="provider_validation_failed",
            )
            self.registry.put(degraded)
            return degraded

        if identity.get("reauth_required") or identity.get("authorized") is False:
            refresh = adapter.refresh_authorization()
            if refresh.get("reauth_required"):
                reauth = replace(
                    record,
                    state=AuthorizationState.REAUTH_REQUIRED,
                    revoked_by_user=False,
                    last_error="interactive_reauthorization_required",
                )
                self.registry.put(reauth)
                return reauth

        if adapter.validate_runtime_credentials(record.runtime_credential_ref, self.vault):
            authorized = replace(
                record,
                state=AuthorizationState.AUTHORIZED,
                revoked_by_user=False,
                last_error=None,
            )
            self.registry.put(authorized)
            return authorized

        refreshing = replace(
            record,
            state=AuthorizationState.REFRESHING,
            revoked_by_user=False,
            last_error=None,
        )
        self.registry.put(refreshing)
        refresh = adapter.refresh_authorization()
        if refresh.get("reauth_required"):
            reauth = replace(
                refreshing,
                state=AuthorizationState.REAUTH_REQUIRED,
                revoked_by_user=False,
                last_error="interactive_reauthorization_required",
            )
            self.registry.put(reauth)
            return reauth

        runtime = adapter.create_runtime_credentials(self.vault)
        runtime_ref = runtime.get("runtime_credential_ref")
        if not runtime_ref or not self.vault.exists(runtime_ref):
            degraded = replace(
                refreshing,
                state=AuthorizationState.DEGRADED,
                revoked_by_user=False,
                last_error="runtime_credential_repair_failed",
            )
            self.registry.put(degraded)
            return degraded

        runtime_id = runtime.get("runtime_credential_id")
        bound_resource = runtime.get("bound_resource")
        authorized = replace(
            refreshing,
            state=AuthorizationState.AUTHORIZED,
            runtime_credential_ref=str(runtime_ref),
            runtime_credential_id=str(runtime_id) if runtime_id is not None else refreshing.runtime_credential_id,
            bound_resource=str(bound_resource) if bound_resource is not None else refreshing.bound_resource,
            revoked_by_user=False,
            last_error=None,
        )
        self.registry.put(authorized)
        return authorized

    def revoke(self, provider_id: str) -> AuthorizationRecord:
        adapter = self._adapter(provider_id)
        record = self.registry.get(provider_id)
        if record is None:
            record = AuthorizationRecord(
                provider_id=provider_id,
                state=AuthorizationState.UNAUTHORIZED,
            )

        runtime_ref = record.runtime_credential_ref
        user_ref = record.user_credential_ref
        runtime_credential_id = record.runtime_credential_id
        bound_resource = record.bound_resource

        if runtime_ref and self.vault.exists(runtime_ref):
            self.vault.delete(runtime_ref)
        if user_ref and self.vault.exists(user_ref):
            self.vault.delete(user_ref)

        revoked = replace(
            record,
            state=AuthorizationState.REVOKED_BY_USER,
            user_credential_ref=None,
            runtime_credential_ref=None,
            revoked_by_user=True,
            acceptance_complete=False,
            last_error=None,
        )
        self.registry.put(revoked)

        remote_incomplete = False
        remote_runtime_revoke = getattr(adapter, "revoke_remote_runtime_credentials", None)
        if callable(remote_runtime_revoke):
            try:
                remote_runtime_revoke(
                    runtime_credential_id=runtime_credential_id,
                    bound_resource=bound_resource,
                )
            except Exception:
                remote_incomplete = True
        try:
            adapter.revoke_runtime_credentials(runtime_ref, self.vault)
        except Exception:
            remote_incomplete = True
        try:
            adapter.revoke_user_authorization()
        except Exception:
            remote_incomplete = True

        if remote_incomplete:
            revoked = replace(revoked, last_error="remote_revocation_incomplete")
            self.registry.put(revoked)
        return revoked
