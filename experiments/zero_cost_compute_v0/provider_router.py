from provider_model import ProviderSnapshot


def eligible_providers(providers: list[ProviderSnapshot]) -> list[ProviderSnapshot]:
    eligible = [
        provider
        for provider in providers
        if provider.authorized
        and provider.healthy
        and provider.zero_cash_cost
        and provider.status == "ready"
    ]
    return sorted(eligible, key=lambda provider: (provider.queue_seconds, -provider.capacity, provider.provider_id))


def route_provider(providers: list[ProviderSnapshot]) -> dict:
    ranked = eligible_providers(providers)
    if not ranked:
        raise RuntimeError("no eligible zero-cash-cost external provider")
    return {
        "primary": ranked[0].provider_id,
        "fallbacks": [provider.provider_id for provider in ranked[1:]],
    }
