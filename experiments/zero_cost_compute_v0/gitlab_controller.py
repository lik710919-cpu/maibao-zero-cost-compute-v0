import json
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from gitlab_provider import (
    BudgetState,
    build_trigger_request,
    check_dispatch_budget,
    pipeline_outcome,
    validate_result,
)


@dataclass(frozen=True)
class GitLabConfig:
    base_url: str
    project_id: str
    ref: str
    job_name: str = "formal_shard"

    def __post_init__(self) -> None:
        if not self.base_url.startswith("https://"):
            raise ValueError("GitLab base URL must use https")
        if not self.project_id:
            raise ValueError("GitLab project ID is required")
        if not self.ref:
            raise ValueError("GitLab ref is required")
        if not self.job_name:
            raise ValueError("GitLab job name is required")


@dataclass(frozen=True)
class GitLabCredentials:
    trigger_token: str
    read_api_token: str


class UrllibGitLabSession:
    def __init__(self, timeout_seconds: int = 30):
        if timeout_seconds <= 0:
            raise ValueError("timeout must be positive")
        self.timeout_seconds = timeout_seconds

    def _open(self, request: Request) -> bytes:
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return response.read()
        except HTTPError as exc:
            raise RuntimeError(f"GitLab API returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError("GitLab API request failed") from exc

    def post_form(self, url: str, form: dict[str, str]) -> Any:
        data = urlencode(form).encode("utf-8")
        request = Request(
            url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return json.loads(self._open(request).decode("utf-8"))

    def get_json(self, url: str, read_token: str) -> Any:
        request = Request(
            url,
            method="GET",
            headers={"PRIVATE-TOKEN": read_token, "Accept": "application/json"},
        )
        return json.loads(self._open(request).decode("utf-8"))

    def get_bytes(self, url: str, read_token: str) -> bytes:
        request = Request(
            url,
            method="GET",
            headers={"PRIVATE-TOKEN": read_token},
        )
        return self._open(request)


def _project_api_base(config: GitLabConfig) -> str:
    project = quote(str(config.project_id), safe="")
    return f"{config.base_url.rstrip('/')}/api/v4/projects/{project}"


def _positive_id(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or value <= 0:
        raise RuntimeError(f"GitLab response missing valid {key}")
    return value


def execute_shard(
    *,
    config: GitLabConfig,
    credentials: GitLabCredentials,
    budget_state: BudgetState,
    assignment: dict[str, Any],
    session: Any | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    max_polls: int = 60,
    poll_interval_seconds: float = 2.0,
) -> dict[str, Any]:
    if not credentials.trigger_token or not credentials.read_api_token:
        raise ValueError("GitLab trigger and read-only API credentials are required")
    if max_polls <= 0:
        raise ValueError("max_polls must be positive")
    if poll_interval_seconds < 0:
        raise ValueError("poll interval must be non-negative")

    budget = check_dispatch_budget(budget_state, shard_count=1)
    if not budget.allowed:
        raise RuntimeError(budget.reason)

    active_session = session or UrllibGitLabSession()
    trigger = build_trigger_request(
        base_url=config.base_url,
        project_id=config.project_id,
        ref=config.ref,
        trigger_token=credentials.trigger_token,
        assignment=assignment,
    )
    triggered = active_session.post_form(trigger.url, trigger.form)
    if not isinstance(triggered, dict):
        raise RuntimeError("GitLab trigger response must be an object")
    pipeline_id = _positive_id(triggered, "id")

    api_base = _project_api_base(config)
    pipeline_url = f"{api_base}/pipelines/{pipeline_id}"
    for attempt in range(max_polls):
        payload = active_session.get_json(pipeline_url, credentials.read_api_token)
        if not isinstance(payload, dict) or payload.get("id") != pipeline_id:
            raise RuntimeError("GitLab pipeline identity mismatch")
        outcome = pipeline_outcome(str(payload.get("status", "")))
        if outcome == "success":
            break
        if outcome == "failure":
            raise RuntimeError("GitLab pipeline failed")
        if attempt + 1 < max_polls:
            sleeper(poll_interval_seconds)
    else:
        raise RuntimeError("GitLab pipeline did not reach a terminal state")

    jobs_url = f"{api_base}/pipelines/{pipeline_id}/jobs"
    jobs = active_session.get_json(jobs_url, credentials.read_api_token)
    if not isinstance(jobs, list):
        raise RuntimeError("GitLab jobs response must be a list")
    matching = [
        item
        for item in jobs
        if isinstance(item, dict)
        and item.get("name") == config.job_name
        and item.get("status") == "success"
    ]
    if len(matching) != 1:
        raise RuntimeError("expected exactly one successful formal GitLab job")
    job_id = _positive_id(matching[0], "id")

    artifact_url = f"{api_base}/jobs/{job_id}/artifacts/out/result.json"
    artifact_bytes = active_session.get_bytes(artifact_url, credentials.read_api_token)
    try:
        result = json.loads(artifact_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("GitLab result artifact is not valid JSON") from exc
    if not isinstance(result, dict):
        raise RuntimeError("GitLab result artifact must be an object")

    return validate_result(
        result,
        expected_assignment=assignment,
        expected_pipeline_id=pipeline_id,
        expected_job_id=job_id,
    )
