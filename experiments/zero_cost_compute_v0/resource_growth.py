import argparse
import json
from pathlib import Path

from provider_qualification import ProviderCandidate, qualify_candidate


CANDIDATE_FIELDS = (
    "provider_id",
    "zero_cash_allowance",
    "hard_quota_stop",
    "requires_billing_account",
    "automatic_overage_possible",
    "authorized_use_confirmed",
    "compute_class",
    "activation_mode",
)


def load_candidates(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("provider registry must contain a list")
    return data


def _candidate_from_record(record: dict) -> ProviderCandidate:
    missing = [field for field in CANDIDATE_FIELDS if field not in record]
    if missing:
        raise ValueError(f"candidate missing required fields: {missing}")
    return ProviderCandidate(**{field: record[field] for field in CANDIDATE_FIELDS})


def build_growth_report(records: list[dict]) -> dict:
    groups = {
        "auto_eligible": [],
        "manual_gate": [],
        "control_only": [],
        "research_only": [],
    }
    details = []

    for record in records:
        candidate = _candidate_from_record(record)
        result = qualify_candidate(candidate)
        groups[result.state].append(candidate.provider_id)
        details.append(
            {
                "provider_id": candidate.provider_id,
                "state": result.state,
                "reasons": list(result.reasons),
                "evidence_url": record.get("evidence_url"),
                "evidence_date": record.get("evidence_date"),
                "quota_summary": record.get("quota_summary"),
                "activation_mode": candidate.activation_mode,
            }
        )

    next_target = groups["auto_eligible"][0] if groups["auto_eligible"] else None
    return {
        **groups,
        "next_adapter_target": next_target,
        "candidate_count": len(records),
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
