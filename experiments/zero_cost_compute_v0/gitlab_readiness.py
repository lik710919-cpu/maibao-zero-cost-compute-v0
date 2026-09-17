#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from gitlab_provider import BudgetState, build_trigger_request, check_dispatch_budget
from gitlab_worker import EXPECTED_RUNNER_TAG, PROVIDER_ID


def build_readiness_evidence(repository_root: str | Path) -> dict:
    root = Path(repository_root)
    required_files = [
        root / ".gitlab-ci.yml",
        root / "experiments/zero_cost_compute_v0/gitlab_provider.py",
        root / "experiments/zero_cost_compute_v0/gitlab_controller.py",
        root / "experiments/zero_cost_compute_v0/gitlab_worker.py",
    ]
    file_status = {str(path.relative_to(root)): path.is_file() for path in required_files}

    budget_state = BudgetState(
        monthly_free_quota_minutes=400,
        starting_monthly_usage_minutes=0,
        adapter_usage_minutes=0,
        reserve_minutes=80,
        max_shard_minutes=5,
    )
    budget = check_dispatch_budget(budget_state, shard_count=1)
    preview = build_trigger_request(
        base_url="https://gitlab.com",
        project_id="AUTHORIZED_PROJECT_ID",
        ref="main",
        trigger_token="REDACTED_CREDENTIAL",
        assignment={
            "index": 0,
            "range_start": 1,
            "range_end": 1000,
            "task_kind": "sum_squares",
            "nonce": "RUNTIME_NONCE",
        },
    ).safe_summary()
    preview.pop("token_present", None)

    stage_a_ready = all(file_status.values()) and budget.allowed
    return {
        "provider_id": PROVIDER_ID,
        "stage_a_adapter_ready": stage_a_ready,
        "stage_b_live_active": False,
        "runner_tag": EXPECTED_RUNNER_TAG,
        "local_formal_compute_percent": 0,
        "zero_new_cash_cost_required": True,
        "file_checks": file_status,
        "budget_guard": {
            "monthly_free_quota_minutes": budget_state.monthly_free_quota_minutes,
            "reserve_minutes": budget_state.reserve_minutes,
            "max_shard_minutes": budget_state.max_shard_minutes,
            "safe_limit_minutes": budget.safe_limit_minutes,
            "one_shard_projected_usage_minutes": budget.projected_usage_minutes,
            "one_shard_allowed": budget.allowed,
        },
        "dispatch_preview": preview,
        "live_blockers": [
            "authorized_gitlab_project",
            "runtime_credentials",
            "verified_current_month_usage_baseline",
            "live_external_shard_evidence",
        ],
        "required_runtime_environment": [
            "MAIBAO_GITLAB_PROJECT_ID",
            "MAIBAO_GITLAB_REF",
            "MAIBAO_GITLAB_TRIGGER_TOKEN",
            "MAIBAO_GITLAB_READ_API_TOKEN",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    evidence = build_readiness_evidence(args.repository_root)
    if not evidence["stage_a_adapter_ready"]:
        return 2
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
