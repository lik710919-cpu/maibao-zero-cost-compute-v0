from dataclasses import dataclass
from typing import Any
from urllib.parse import quote


PROVIDER_ID = "gitlab-hosted-runners"
TERMINAL_SUCCESS = {"success"}
TERMINAL_FAILURE = {"failed", "canceled", "cancelled", "skipped", "manual"}
PENDING_STATUSES = {"created", "waiting_for_resource", "preparing", "pending", "running", "scheduled"}


@dataclass(frozen=True)
class BudgetState:
    monthly_free_quota_minutes: int
    starting_monthly_usage_minutes: int
    adapter_usage_minutes: int
    reserve_minutes: int
    max_shard_minutes: int

    def __post_init__(self) -> None:
        if self.monthly_free_quota_minutes <= 0:
            raise ValueError("monthly free quota must be positive")
        if self.starting_monthly_usage_minutes < 0:
            raise ValueError("starting monthly usage must be non-negative")
        if self.adapter_usage_minutes < 0:
            raise ValueError("adapter usage must be non-negative")
        if self.reserve_minutes <= 0:
            raise ValueError("reserve minutes must be positive")
        if self.reserve_minutes >= self.monthly_free_quota_minutes:
            raise ValueError("reserve must be smaller than free quota")
        if self.max_shard_minutes <= 0:
            raise ValueError("max shard minutes must be positive")


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    projected_usage_minutes: int
    safe_limit_minutes: int
    reason: str


@dataclass(frozen=True)
class TriggerRequest:
    method: str
    url: str
    form: dict[str, str]

    def safe_summary(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "url": self.url,
            "form": {key: value for key, value in self.form.items() if key != "token"},
            "token_present": bool(self.form.get("token")),
        }


def check_dispatch_budget(state: BudgetState, shard_count: int) -> BudgetDecision:
    if shard_count <= 0:
        raise ValueError("shard count must be positive")
    safe_limit = state.monthly_free_quota_minutes - state.reserve_minutes
    projected = (
        state.starting_monthly_usage_minutes
        + state.adapter_usage_minutes
        + shard_count * state.max_shard_minutes
    )
    if projected > safe_limit:
        return BudgetDecision(
            False,
            projected,
            safe_limit,
            "projected usage exceeds safe free-minute budget",
        )
    return BudgetDecision(True, projected, safe_limit, "within safe free-minute budget")


def _validated_assignment(assignment: dict[str, Any]) -> dict[str, Any]:
    required = ("index", "range_start", "range_end", "task_kind", "nonce")
    missing = [key for key in required if key not in assignment]
    if missing:
        raise ValueError(f"assignment missing required fields: {missing}")
    index = assignment["index"]
    start = assignment["range_start"]
    end = assignment["range_end"]
    if not isinstance(index, int) or index < 0:
        raise ValueError("invalid shard index")
    if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start:
        raise ValueError("invalid shard bounds")
    if assignment["task_kind"] != "sum_squares":
        raise ValueError("unsupported task kind")
    nonce = assignment["nonce"]
    if not isinstance(nonce, str) or not nonce or len(nonce) > 128:
        raise ValueError("invalid nonce")
    return assignment


def build_trigger_request(
    *,
    base_url: str,
    project_id: str,
    ref: str,
    trigger_token: str,
    assignment: dict[str, Any],
) -> TriggerRequest:
    if not base_url.startswith("https://"):
        raise ValueError("GitLab base URL must use https")
    if not project_id:
        raise ValueError("project id is required")
    if not ref:
        raise ValueError("ref is required")
    if not trigger_token:
        raise ValueError("trigger token is required")
    item = _validated_assignment(assignment)
    encoded_project = quote(str(project_id), safe="")
    url = f"{base_url.rstrip('/')}/api/v4/projects/{encoded_project}/trigger/pipeline"
    form = {
        "token": trigger_token,
        "ref": ref,
        "variables[MAIBAO_PROVIDER_ID]": PROVIDER_ID,
        "variables[MAIBAO_CHUNK_INDEX]": str(item["index"]),
        "variables[MAIBAO_RANGE_START]": str(item["range_start"]),
        "variables[MAIBAO_RANGE_END]": str(item["range_end"]),
        "variables[MAIBAO_TASK_KIND]": item["task_kind"],
        "variables[MAIBAO_NONCE]": item["nonce"],
    }
    return TriggerRequest("POST", url, form)


def pipeline_outcome(status: str) -> str:
    normalized = (status or "").strip().lower()
    if normalized in TERMINAL_SUCCESS:
        return "success"
    if normalized in PENDING_STATUSES:
        return "pending"
    if normalized in TERMINAL_FAILURE:
        return "failure"
    return "failure"


def validate_result(
    result: dict[str, Any],
    *,
    expected_assignment: dict[str, Any],
    expected_pipeline_id: int,
    expected_job_id: int,
) -> dict[str, Any]:
    assignment = _validated_assignment(expected_assignment)
    expected = {
        "provider_id": PROVIDER_ID,
        "pipeline_id": expected_pipeline_id,
        "job_id": expected_job_id,
        "chunk_index": assignment["index"],
        "range_start": assignment["range_start"],
        "range_end": assignment["range_end"],
        "nonce": assignment["nonce"],
        "local_compute_used": False,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise ValueError(f"result {key} mismatch")
    partial_sum = result.get("partial_sum")
    if not isinstance(partial_sum, int) or partial_sum < 0:
        raise ValueError("invalid partial_sum")
    return result
