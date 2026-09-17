from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderSnapshot:
    provider_id: str
    authorized: bool
    healthy: bool
    zero_cash_cost: bool
    queue_seconds: float
    capacity: int
    evidence: str
    status: str
