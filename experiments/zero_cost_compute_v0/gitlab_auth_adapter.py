from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any, Sequence

from authorization_core import AuthorizationSession


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class SubprocessCommandRunner:
    def run(self, args: Sequence[str], *, capture: bool = True) -> CommandResult:
        if capture:
            completed = subprocess.run(
                list(args),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        else:
            completed = subprocess.run(list(args), text=True, check=False)
        return CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )


class GitLabAuthAdapter:
    provider_id = "gitlab"

    def __init__(self, *, hostname: str = "gitlab.com", runner: Any | None = None) -> None:
        if not hostname or "/" in hostname:
            raise ValueError("GitLab hostname is invalid")
        self.hostname = hostname
        self.runner = runner or SubprocessCommandRunner()

    def _run(self, args: list[str], *, capture: bool = True) -> Any:
        result = self.runner.run(args, capture=capture)
        if result.returncode != 0:
            detail = (getattr(result, "stderr", "") or "").strip()
            raise RuntimeError(detail or "GitLab CLI command failed")
        return result

    def begin_authorization(self) -> AuthorizationSession:
        self._run(
            ["glab", "auth", "login", "--hostname", self.hostname, "--device"],
            capture=False,
        )
        return AuthorizationSession(
            provider_id=self.provider_id,
            verification_uri=f"https://{self.hostname}/oauth/device",
        )

    def poll_authorization(self) -> dict[str, Any]:
        try:
            return self.validate_identity()
        except RuntimeError:
            return {"authorized": False}

    def validate_identity(self) -> dict[str, Any]:
        result = self._run(
            ["glab", "api", "user", "--hostname", self.hostname, "--output", "json"],
            capture=True,
        )
        try:
            payload = json.loads(result.stdout)
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("GitLab identity response is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("GitLab identity response must be an object")
        user_id = payload.get("id")
        username = payload.get("username")
        if not isinstance(user_id, int) or user_id <= 0 or not isinstance(username, str) or not username:
            raise RuntimeError("GitLab identity response is incomplete")
        return {
            "authorized": True,
            "account_id": str(user_id),
            "username": username,
            "display_name": str(payload.get("name") or username),
            "provider": self.provider_id,
            "hostname": self.hostname,
        }

    def inspect_scopes(self) -> list[str]:
        # The built-in glab OAuth application owns the exact account-level scopes.
        # Keep registry evidence conservative instead of copying any token material.
        return ["gitlab_cli_oauth"]

    def refresh_authorization(self) -> dict[str, Any]:
        try:
            identity = self.validate_identity()
        except RuntimeError:
            return {"authorized": False, "reauth_required": True}
        return {"authorized": True, "account_id": identity["account_id"]}

    def create_runtime_credentials(self, vault: Any) -> dict[str, Any]:
        raise RuntimeError("GitLab runtime credential bootstrap is not configured yet")

    def validate_runtime_credentials(self, runtime_ref: str | None, vault: Any) -> bool:
        return bool(runtime_ref) and vault.exists(runtime_ref)

    def revoke_runtime_credentials(self, runtime_ref: str | None, vault: Any) -> None:
        if runtime_ref and vault.exists(runtime_ref):
            vault.delete(runtime_ref)

    def revoke_user_authorization(self) -> None:
        result = self.runner.run(
            ["glab", "auth", "logout", "--hostname", self.hostname],
            capture=True,
        )
        if result.returncode != 0:
            raise RuntimeError("GitLab CLI logout failed")
