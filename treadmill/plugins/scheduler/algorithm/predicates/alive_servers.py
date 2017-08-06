from treadmill.plugins.scheduler import predicates
from treadmill.sched import utils


class AliveServers(predicates.PredicateConfig):
    def predicate(self, app, node):
        if node.state is utils.State.up:
            return True
        return False


def alive_servers():
    return AliveServers()
