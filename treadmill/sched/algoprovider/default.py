from .provider import Provider


def default_provider():
    provider = Provider()
    provider.register_predicates('match_app_constraints')
    provider.register_predicates('match_app_lifetime')
    provider.register_priorities('spread', 1)
    return provider
