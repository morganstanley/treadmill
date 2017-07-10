from .provider import Provider
from ..algorithm import predicates
from ..algorithm import priorities


def default_provider():
    provider = Provider()
    provider.register_predicates("MatchAppConstrains", predicates.MatchAppConstrains())
    provider.register_priorities("least_requests", priorities.LeastRequests(1))
    return provider
