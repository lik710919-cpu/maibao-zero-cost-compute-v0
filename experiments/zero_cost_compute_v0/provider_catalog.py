from provider_model import ProviderSnapshot
from provider_router import eligible_providers, route_provider


def build_catalog(
    providers: list[ProviderSnapshot],
    execution_provider_ids: list[str] | None = None,
) -> dict:
    live = eligible_providers(providers)
    live_ids = [provider.provider_id for provider in live]
    live_id_set = set(live_ids)

    execution_ids: list[str] = []
    for provider_id in execution_provider_ids or []:
        if provider_id in live_id_set and provider_id not in execution_ids:
            execution_ids.append(provider_id)

    route = route_provider(live) if live else None
    return {
        "live_provider_count": len(live_ids),
        "live_provider_ids": live_ids,
        "execution_provider_ids": execution_ids,
        "local_formal_compute_percent": 0,
        "route": route,
        "cross_provider_closed": len(execution_ids) >= 2,
    }
