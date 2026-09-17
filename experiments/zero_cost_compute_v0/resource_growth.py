import argparse
import json
from pathlib import Path

from authorization_ingress import AuthorizationRoute, authorization_policy_from_candidate
from authorization_profiles import apply_profile
from provider_qualification import ProviderCandidate, qualify_candidate


BASE_CANDIDATE_FIELDS = (
    "provider_id",
    "zero_cash_allowance",
    "hard_quota_stop",
    "requires_billing_account",
    "automatic_overage_possible",
    "authorized_use_confirmed",
    "compute_class",
    "activation_mode",
)

OPTIONAL_POLICY_FIELDS = (
    "terms_scope",
    "terms_scope_confirmed",
    "external_authorization_required",
    "formal_pool_eligible",
)


def load_candidates(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("provider registry must contain a list")
    return data


def _candidate_from_record(record: dict) -> ProviderCandidate:
    missing = [field for field in BASE_CANDIDATE_FIELDS if field not in record]
    if missing:
        raise ValueError(f"candidate missing required fields: {missing}")
    values = {field: record[field] for field in BASE_CANDIDATE_FIELDS}
    for field in OPTIONAL_POLICY_FIELDS:
        if field in record:
            values[field] = record[field]
    return ProviderCandidate(**values)


def _research_priority(record: dict) -> tuple[int, int]:
    priority = record.get("research_priority", 0)
    minutes = record.get("advertised_monthly_capacity_minutes") or 0
    if not isinstance(priority, int):
        priority = 0
    if not isinstance(minutes, int):
        minutes = 0
    return priority, minutes


def build_growth_report(records: list[dict]) -> dict:
    groups = {
        "auto_eligible": [],
        "manual_gate": [],
        "control_only": [],
        "research_only": [],
        "policy_gate": [],
        "developer_environment": [],
    }
    lifecycle = {
        "researched": [],
        "adapter_ready": [],
        "live_active": [],
    }
    authorization_routes = {
        "unified_authorization_required": [],
        "authorization_discovery_required": [],
        "authorization_exception_allowed": [],
        "authorization_not_required": [],
    }
    route_to_group = {
        AuthorizationRoute.UNIFIED_REQUIRED: "unified_authorization_required",
        AuthorizationRoute.DISCOVERY_REQUIRED: "authorization_discovery_required",
        AuthorizationRoute.EXCEPTION_ALLOWED: "authorization_exception_allowed",
        AuthorizationRoute.NOT_REQUIRED: "authorization_not_required",
    }
    details = []
    adapter_candidates = []
    research_candidates = []

    for raw_record in records:
        record = apply_profile(raw_record)
        candidate = _candidate_from_record(record)
        result = qualify_candidate(candidate)
        groups[result.state].append(candidate.provider_id)

        auth_decision = authorization_policy_from_candidate(record)
        authorization_routes[route_to_group[auth_decision.route]].append(candidate.provider_id)

        lifecycle_state = record.get("lifecycle_state", "researched")
        if lifecycle_state not in lifecycle:
            lifecycle_state = "researched"
        lifecycle[lifecycle_state].append(candidate.provider_id)

        if result.state == "auto_eligible" and lifecycle_state == "researched":
            adapter_candidates.append(record)
        elif lifecycle_state == "researched" and result.state in {
            "policy_gate",
            "developer_environment",
            "manual_gate",
            "research_only",
        }:
            research_candidates.append(record)

        details.append(
            {
                "provider_id": candidate.provider_id,
                "authorization_provider_id": record["authorization_provider_id"],
                "state": result.state,
                "lifecycle_state": lifecycle_state,
                "reasons": list(result.reasons),
                "evidence_url": record.get("evidence_url"),
                "evidence_date": record.get("evidence_date"),
                "quota_summary": record.get("quota_summary"),
                "activation_mode": candidate.activation_mode,
                "terms_scope": candidate.terms_scope,
                "terms_scope_confirmed": candidate.terms_scope_confirmed,
                "formal_pool_eligible": candidate.formal_pool_eligible,
                "advertised_monthly_capacity_minutes": record.get("advertised_monthly_capacity_minutes"),
                "advertised_monthly_core_hours": record.get("advertised_monthly_core_hours"),
                "capacity_visibility": record.get("capacity_visibility", "unknown"),
                "authorization_required": record["authorization_required"],
                "supports_persistent_authorization": record["supports_persistent_authorization"],
                "authorization_route": auth_decision.route.value,
                "authorization_intercept": auth_decision.intercept,
                "authorization_reason": auth_decision.reason,
            }
        )

    adapter_candidates.sort(key=_research_priority, reverse=True)
    research_candidates.sort(key=_research_priority, reverse=True)
    next_adapter_target = adapter_candidates[0]["provider_id"] if adapter_candidates else None
    next_research_target = research_candidates[0]["provider_id"] if research_candidates else None

    return {
        **groups,
        **lifecycle,
        **authorization_routes,
        "next_adapter_target": next_adapter_target,
        "next_research_target": next_research_target,
        "candidate_count": len(records),
        "active_capacity_claimed": False,
        "local_formal_compute_percent": 0,
        "details": details,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    report = build_growth_report(load_candidates(args.registry))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
