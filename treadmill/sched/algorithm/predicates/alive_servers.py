from ...predicates import PredicateConfig
from ...utils import State


class AliveServers(PredicateConfig):
    def predicate(self, app, node):
        if node.state is State.up:
            return True
        return False


def alive_servers():
    return AliveServers()
