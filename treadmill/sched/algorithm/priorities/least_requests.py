import logging
import sys

from ...priorities import PriorityConfig, ServerWithPriority

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


class LeastRequests(PriorityConfig):
    def map(self, app, node):
        _LOGGER.debug("least_requests_map_function")
        # TODO: Implement the real logic
        return ServerWithPriority(1, node)

    def reduce(self, app, nodes, result):
        pass


def least_requests(weight):
    return LeastRequests(weight)
