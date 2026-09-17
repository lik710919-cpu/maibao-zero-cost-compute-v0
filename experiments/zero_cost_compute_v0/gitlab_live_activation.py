from __future__ import annotations

import json
from typing import Any, Callable
from urllib.parse import urlparse

from gitlab_controller import GitLabConfig, GitLabCredentials, UrllibGitLabSession, execute_shard
from gitlab_provider import BudgetState, PROVIDER_ID


class GlabAuthenticatedSession:
    """Read GitLab APIs through glab's stored OAuth context; use trigger token only for dispatch."""

    def __init__(self, *, runner: Any, hostname: str = "gitlab.com", trigger_session: Any | None = None) -> None:
        self.runner = runner
        self.hostname = hostname
        self.trigger_session = trigger_session or UrllibGitLabSession()

    @staticmethod
    def _endpoint(url: str) -> str:
        parsed = urlparse(url)
        marker = "/api/v4/"
        if marker not in parsed.path:
            raise ValueError("GitLab API URL is outside /api/v4")
        endpoint = parsed.path.split(marker, 1)[1]
        if parsed.query:
            endpoint = f"{endpoint}?{parsed.query}"
        return endpoint

    def _run(self, endpoint: str, *, json_output: bool) -> str:
        args = ["glab", "api", endpoint, "--hostname", self.hostname]
        if json_output:
            args.extend(["--output", "json"])
        result = self.runner.run(args, capture=True)
        if result.returncode != 0:
            detail = (getattr(result, "stderr", "") or "").strip()
            raise RuntimeError(detail or "GitLab API request through glab failed")
        return result.stdout

    def post_form(self, url: str, form: dict[str, str]) -> Any:
        return self.trigger_session.post_form(url, form)

    def get_json(self, url: str, read_token: str) -> Any:
        del read_token
        return json.loads(self._run(self._endpoint(url), json_output=True))

    def get_bytes(self, url: str, read_token: str) -> bytes:
        del read_token
        return self._run(self._endpoint(url), json_output=False).encode("utf-8")


class GitLabLiveActivationProbe:
    def __init__(
        self,
        *,
        vault: Any,
        runner: Any,
        execute: Callable[..., dict[str, Any]] = execute_shard,
        hostname: str = "gitlab.com",
        monthly_free_quota_minutes: int = 400,
        reserve_minutes: int = 80,
        max_shard_minutes: int = 5,
    ) -> None:
        self.vault = vault
        self.runner = runner
        self.execute = execute
        self.hostname = hostname
        self.monthly_free_quota_minutes = monthly_free_quota_minutes
        self.reserve_minutes = reserve_minutes
        self.max_shard_minutes = max_shard_minutes

    def _api_json(self, endpoint: str) -> Any:
        result = self.runner.run(
            ["glab", "api", endpoint, "--hostname", self.hostname, "--output", "json"],
            capture=True,
        )
        if result.returncode != 0:
            detail = (getattr(result, "stderr", "") or "").strip()
            raise RuntimeError(detail or "GitLab API request through glab failed")
        try:
            return json.loads(result.stdout)
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("GitLab API response is not valid JSON") from exc

    @staticmethod
    def _sum_squares(start: int, end: int) -> int:
        def prefix(value: int) -> int:
            return value * (value + 1) * (2 * value + 1) // 6

        return prefix(end) - prefix(start - 1)

    def __call__(self, record: Any) -> dict[str, Any]:
        project_id = str(record.bound_resource or "")
        runtime_ref = record.runtime_credential_ref
        if not project_id or not runtime_ref:
            raise RuntimeError("GitLab live activation requires bound project and runtime credential")

        project = self._api_json(f"projects/{project_id}")
        if not isinstance(project, dict):
            raise RuntimeError("GitLab project response must be an object")
        namespace = project.get("namespace")
        namespace_id = namespace.get("id") if isinstance(namespace, dict) else None
        default_branch = project.get("default_branch") or "main"
        if not isinstance(namespace_id, int) or namespace_id <= 0:
            raise RuntimeError("GitLab project namespace is missing")
        if not isinstance(default_branch, str) or not default_branch:
            raise RuntimeError("GitLab project default branch is missing")

        namespace_detail = self._api_json(f"namespaces/{namespace_id}")
        if not isinstance(namespace_detail, dict):
            raise RuntimeError("GitLab namespace response must be an object")
        usage = namespace_detail.get("ci_minutes_usage")
        monthly_used = usage.get("monthly_minutes_used") if isinstance(usage, dict) else None
        if not isinstance(monthly_used, int) or monthly_used < 0:
            raise RuntimeError("GitLab compute usage is not visible; activation fails closed")

        budget = BudgetState(
            monthly_free_quota_minutes=self.monthly_free_quota_minutes,
            starting_monthly_usage_minutes=monthly_used,
            adapter_usage_minutes=0,
            reserve_minutes=self.reserve_minutes,
            max_shard_minutes=self.max_shard_minutes,
        )
        assignment = {
            "index": 0,
            "range_start": 1,
            "range_end": 1000,
            "task_kind": "sum_squares",
            "nonce": "activation-probe",
        }
        trigger_token = self.vault.get(runtime_ref)
        if not isinstance(trigger_token, str) or not trigger_token:
            raise RuntimeError("GitLab runtime trigger credential is unavailable")

        result = self.execute(
            config=GitLabConfig(
                base_url=f"https://{self.hostname}",
                project_id=project_id,
                ref=default_branch,
            ),
            credentials=GitLabCredentials(
                trigger_token=trigger_token,
                read_api_token="oauth-via-glab-keyring",
            ),
            budget_state=budget,
            assignment=assignment,
            session=GlabAuthenticatedSession(runner=self.runner, hostname=self.hostname),
        )
        if result.get("provider_id") != PROVIDER_ID or result.get("local_compute_used") is not False:
            raise RuntimeError("GitLab external provider identity verification failed")
        expected_sum = self._sum_squares(assignment["range_start"], assignment["range_end"])
        if result.get("partial_sum") != expected_sum:
            raise RuntimeError("GitLab external shard sum verification failed")

        return {
            "verified": True,
            "provider_id": PROVIDER_ID,
            "project_id": project_id,
            "namespace_id": namespace_id,
            "namespace_monthly_minutes_used": monthly_used,
            "monthly_free_quota_minutes": self.monthly_free_quota_minutes,
            "reserve_minutes": self.reserve_minutes,
            "pipeline_id": result.get("pipeline_id"),
            "job_id": result.get("job_id"),
            "chunk_index": result.get("chunk_index"),
            "range_start": result.get("range_start"),
            "range_end": result.get("range_end"),
            "partial_sum": result.get("partial_sum"),
            "local_compute_used": False,
        }
