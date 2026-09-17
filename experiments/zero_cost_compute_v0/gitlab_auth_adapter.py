from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import quote, urlencode

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
    _PROJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,98}[A-Za-z0-9]$")
    _COMPUTE_BUNDLE = (
        ".gitlab-ci.yml",
        "experiments/zero_cost_compute_v0/gitlab_worker.py",
    )

    def __init__(
        self,
        *,
        hostname: str = "gitlab.com",
        runner: Any | None = None,
        project_id: str | None = None,
        project_name: str = "maibao-external-compute",
        source_root: str | Path | None = None,
    ) -> None:
        if not hostname or "/" in hostname:
            raise ValueError("GitLab hostname is invalid")
        if not isinstance(project_name, str) or not self._PROJECT_RE.fullmatch(project_name):
            raise ValueError("GitLab project name is invalid")
        self.hostname = hostname
        self.runner = runner or SubprocessCommandRunner()
        self.project_id = str(project_id) if project_id else None
        self.project_name = project_name
        self.source_root = Path(source_root) if source_root is not None else Path(__file__).resolve().parents[2]

    def _run(self, args: list[str], *, capture: bool = True) -> Any:
        result = self.runner.run(args, capture=capture)
        if result.returncode != 0:
            detail = (getattr(result, "stderr", "") or "").strip()
            raise RuntimeError(detail or "GitLab CLI command failed")
        return result

    @staticmethod
    def _json_object(result: Any, label: str) -> dict[str, Any]:
        try:
            payload = json.loads(result.stdout)
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"{label} is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"{label} must be an object")
        return payload

    @staticmethod
    def _json_list(result: Any, label: str) -> list[Any]:
        try:
            payload = json.loads(result.stdout)
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"{label} is not valid JSON") from exc
        if not isinstance(payload, list):
            raise RuntimeError(f"{label} must be a list")
        return payload

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
            identity = self.validate_identity()
        except RuntimeError:
            return {"authorized": False}
        return {
            **identity,
            "scopes": self.inspect_scopes(),
        }

    def validate_identity(self) -> dict[str, Any]:
        result = self._run(
            ["glab", "api", "user", "--hostname", self.hostname, "--output", "json"],
            capture=True,
        )
        payload = self._json_object(result, "GitLab identity response")
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
        return ["gitlab_cli_oauth"]

    def refresh_authorization(self) -> dict[str, Any]:
        try:
            identity = self.validate_identity()
        except RuntimeError:
            return {"authorized": False, "reauth_required": True}
        return {"authorized": True, "account_id": identity["account_id"]}

    def ensure_project(self, project_name: str) -> dict[str, str]:
        if not isinstance(project_name, str) or not self._PROJECT_RE.fullmatch(project_name):
            raise ValueError("GitLab project name is invalid")

        query = urlencode({"owned": "true", "search": project_name})
        listed = self._run(
            [
                "glab",
                "api",
                f"projects?{query}",
                "--hostname",
                self.hostname,
                "--output",
                "json",
            ],
            capture=True,
        )
        projects = self._json_list(listed, "GitLab project search response")
        exact = [
            item
            for item in projects
            if isinstance(item, dict)
            and (item.get("path") == project_name or item.get("name") == project_name)
        ]
        if len(exact) > 1:
            raise RuntimeError("multiple exact GitLab projects matched the requested name")

        if exact:
            payload = exact[0]
        else:
            created = self._run(
                [
                    "glab",
                    "api",
                    "projects",
                    "--hostname",
                    self.hostname,
                    "--method",
                    "POST",
                    "--raw-field",
                    f"name={project_name}",
                    "--raw-field",
                    f"path={project_name}",
                    "--raw-field",
                    "visibility=private",
                    "--raw-field",
                    "initialize_with_readme=true",
                    "--output",
                    "json",
                ],
                capture=True,
            )
            payload = self._json_object(created, "GitLab project create response")

        project_id = payload.get("id")
        path_with_namespace = payload.get("path_with_namespace")
        default_branch = payload.get("default_branch") or "main"
        if not isinstance(project_id, int) or project_id <= 0:
            raise RuntimeError("GitLab project response is missing a valid id")
        if not isinstance(path_with_namespace, str) or not path_with_namespace:
            raise RuntimeError("GitLab project response is missing path_with_namespace")
        if not isinstance(default_branch, str) or not default_branch:
            raise RuntimeError("GitLab project response is missing default_branch")

        self.project_id = str(project_id)
        return {
            "project_id": str(project_id),
            "path_with_namespace": path_with_namespace,
            "default_branch": default_branch,
        }

    def _repository_file_endpoint(self, project_id: str, file_path: str, branch: str) -> str:
        project = quote(str(project_id), safe="")
        encoded_path = quote(file_path, safe="")
        return f"projects/{project}/repository/files/{encoded_path}?{urlencode({'ref': branch})}"

    def ensure_compute_bundle(
        self,
        *,
        project_id: str,
        default_branch: str,
        source_root: str | Path,
    ) -> dict[str, Any]:
        if not project_id or not default_branch:
            raise ValueError("project id and default branch are required")
        root = Path(source_root)
        synced = []

        for relative_path in self._COMPUTE_BUNDLE:
            source = root / relative_path
            if not source.is_file():
                raise FileNotFoundError(f"required compute bundle file is missing: {relative_path}")
            content = source.read_text(encoding="utf-8")
            endpoint = self._repository_file_endpoint(project_id, relative_path, default_branch)
            probe = self.runner.run(
                ["glab", "api", endpoint, "--hostname", self.hostname, "--output", "json"],
                capture=True,
            )
            if probe.returncode == 0:
                method = "PUT"
            else:
                detail = (getattr(probe, "stderr", "") or "").lower()
                if "404" not in detail and "not found" not in detail:
                    raise RuntimeError("failed to inspect GitLab compute bundle file")
                method = "POST"

            write_endpoint = endpoint.split("?", 1)[0]
            self._run(
                [
                    "glab",
                    "api",
                    write_endpoint,
                    "--hostname",
                    self.hostname,
                    "--method",
                    method,
                    "--raw-field",
                    f"branch={default_branch}",
                    "--raw-field",
                    f"commit_message=maibao: sync {relative_path}",
                    "--raw-field",
                    f"content={content}",
                    "--output",
                    "json",
                ],
                capture=True,
            )
            synced.append(relative_path)

        self.project_id = str(project_id)
        return {"project_id": str(project_id), "synced_files": len(synced), "files": synced}

    def create_runtime_credentials(
        self,
        vault: Any = None,
        *,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        if vault is None:
            raise ValueError("credential vault is required")

        effective_project = str(project_id or self.project_id or "")
        if not effective_project:
            project = self.ensure_project(self.project_name)
            effective_project = project["project_id"]
            self.ensure_compute_bundle(
                project_id=effective_project,
                default_branch=project["default_branch"],
                source_root=self.source_root,
            )

        endpoint = f"projects/{quote(effective_project, safe='')}/triggers"
        created = self._run(
            [
                "glab",
                "api",
                endpoint,
                "--hostname",
                self.hostname,
                "--method",
                "POST",
                "--raw-field",
                "description=maibao-formal-compute",
                "--output",
                "json",
            ],
            capture=True,
        )
        payload = self._json_object(created, "GitLab pipeline trigger response")
        trigger_id = payload.get("id")
        trigger_secret = payload.get("token")
        if not isinstance(trigger_id, int) or trigger_id <= 0:
            raise RuntimeError("GitLab pipeline trigger response is missing a valid id")
        if not isinstance(trigger_secret, str) or not trigger_secret:
            raise RuntimeError("GitLab pipeline trigger response is missing the trigger secret")
        runtime_ref = vault.put(
            f"gitlab/{effective_project}/pipeline-trigger",
            trigger_secret,
        )
        self.project_id = effective_project
        return {
            "runtime_credential_ref": runtime_ref,
            "runtime_credential_id": str(trigger_id),
            "bound_resource": effective_project,
        }

    def validate_runtime_credentials(self, runtime_ref: str | None, vault: Any) -> bool:
        return bool(runtime_ref) and vault.exists(runtime_ref)

    def revoke_runtime_credentials(self, runtime_ref: str | None, vault: Any) -> None:
        if runtime_ref and vault.exists(runtime_ref):
            vault.delete(runtime_ref)

    def revoke_remote_runtime_credentials(
        self,
        *,
        runtime_credential_id: str | None,
        bound_resource: str | None,
    ) -> None:
        if not runtime_credential_id or not bound_resource:
            return
        if not str(runtime_credential_id).isdigit() or not str(bound_resource).isdigit():
            raise ValueError("GitLab trigger and project IDs must be numeric")
        endpoint = f"projects/{quote(str(bound_resource), safe='')}/triggers/{quote(str(runtime_credential_id), safe='')}"
        self._run(
            [
                "glab",
                "api",
                endpoint,
                "--hostname",
                self.hostname,
                "--method",
                "DELETE",
                "--silent",
            ],
            capture=True,
        )

    def revoke_user_authorization(self) -> None:
        result = self.runner.run(
            ["glab", "auth", "logout", "--hostname", self.hostname],
            capture=True,
        )
        if result.returncode != 0:
            raise RuntimeError("GitLab CLI logout failed")
