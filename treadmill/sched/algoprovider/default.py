from .provider import Provider


def default_provider():
    provider = Provider()
    provider.register_predicates('match_app_constraints')
    provider.register_priorities('least_requests', 1)
    return provider
