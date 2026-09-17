from provider_model import ProviderSnapshot
from provider_router import eligible_providers, route_provider


def build_catalog(providers: list[ProviderSnapshot]) -> dict:
    live = eligible_providers(providers)
    live_ids = [provider.provider_id for provider in live]
    route = route_provider(live) if live else None
    return {
        "live_provider_count": len(live_ids),
        "live_provider_ids": live_ids,
        "local_formal_compute_percent": 0,
        "route": route,
        "cross_provider_closed": len(set(live_ids)) >= 2,
    }
