from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderCandidate:
    provider_id: str
    zero_cash_allowance: bool
    hard_quota_stop: bool
    requires_billing_account: bool
    automatic_overage_possible: bool
    authorized_use_confirmed: bool
    compute_class: str
    activation_mode: str
    terms_scope: str = "general_compute"
    terms_scope_confirmed: bool = True
    external_authorization_required: bool = False
    formal_pool_eligible: bool = True


@dataclass(frozen=True)
class QualificationResult:
    provider_id: str
    state: str
    reasons: tuple[str, ...]


def qualify_candidate(candidate: ProviderCandidate) -> QualificationResult:
    if not candidate.zero_cash_allowance:
        return QualificationResult(candidate.provider_id, "research_only", ("no_zero_cash_allowance",))
    if not candidate.authorized_use_confirmed:
        return QualificationResult(candidate.provider_id, "research_only", ("authorization_not_confirmed",))
    if candidate.compute_class == "control_only" or candidate.terms_scope == "control_only":
        return QualificationResult(candidate.provider_id, "control_only", ("not_suitable_for_formal_compute",))
    if candidate.terms_scope == "developer_environment":
        return QualificationResult(
            candidate.provider_id,
            "developer_environment",
            ("developer_environment_not_general_pool",),
        )
    if (
        not candidate.terms_scope_confirmed
        or not candidate.formal_pool_eligible
        or candidate.terms_scope != "general_compute"
    ):
        return QualificationResult(
            candidate.provider_id,
            "policy_gate",
            ("terms_scope_not_confirmed_for_general_formal_compute",),
        )
    if (
        candidate.external_authorization_required
        or candidate.requires_billing_account
        or candidate.automatic_overage_possible
        or not candidate.hard_quota_stop
    ):
        return QualificationResult(candidate.provider_id, "manual_gate", ("cash_or_authorization_gate",))
    return QualificationResult(candidate.provider_id, "auto_eligible", ("policy_safe_fail_closed_zero_cash_quota",))
