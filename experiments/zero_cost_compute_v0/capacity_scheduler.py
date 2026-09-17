from dataclasses import dataclass
from collections import Counter


@dataclass(frozen=True)
class ProviderPolicy:
    provider_id: str
    capacity: int
    max_tasks_per_run: int | None
    priority: int = 0

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must be non-empty")
        if self.capacity < 1:
            raise ValueError("capacity must be positive")
        if self.max_tasks_per_run is not None and self.max_tasks_per_run < 1:
            raise ValueError("max_tasks_per_run must be positive when set")


def assignment_counts(assignments: list[dict]) -> dict[str, int]:
    return dict(Counter(item["provider_id"] for item in assignments))


def assign_shards(shard_count: int, policies: list[ProviderPolicy]) -> list[dict]:
    if shard_count < 1:
        raise ValueError("shard_count must be positive")
    if not policies:
        raise ValueError("at least one provider policy is required")

    ordered = sorted(policies, key=lambda item: (item.priority, item.provider_id))
    provider_ids = [item.provider_id for item in ordered]
    if len(provider_ids) != len(set(provider_ids)):
        raise ValueError("provider_id values must be unique")

    assigned_counts = {item.provider_id: 0 for item in ordered}
    assignments: list[dict] = []

    while len(assignments) < shard_count:
        made_progress = False
        for policy in ordered:
            remaining_budget = (
                shard_count
                if policy.max_tasks_per_run is None
                else policy.max_tasks_per_run - assigned_counts[policy.provider_id]
            )
            if remaining_budget <= 0:
                continue

            take = min(policy.capacity, remaining_budget, shard_count - len(assignments))
            for _ in range(take):
                assignments.append(
                    {
                        "index": len(assignments),
                        "provider_id": policy.provider_id,
                    }
                )
                assigned_counts[policy.provider_id] += 1
                made_progress = True

            if len(assignments) == shard_count:
                break

        if not made_progress:
            raise RuntimeError("provider task budgets cannot cover all shards")

    return assignments
