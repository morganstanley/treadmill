import logging
import queue
import sys
import importlib

from treadmill.plugins.scheduler import priorities

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


class Provider(object):
    """Algorithm provider"""
    __slots__ = (
        'predicates_functions',
        'priorities_functions',
    )

    PRECOCATES_CLASS_PREFIX = \
        'treadmill.plugins.scheduler.algorithm.predicates'
    PRIORITIES_CLASS_PREFIX = \
        'treadmill.plugins.scheduler.algorithm.priorities'

    def __init__(self):
        self.predicates_functions = []
        self.priorities_functions = []

    def register_priorities(self, name, weight):
        mod = importlib.import_module(Provider.PRIORITIES_CLASS_PREFIX)
        priority_create_function = getattr(mod, name)
        self.priorities_functions.append({
            'name': name,
            'priority': priority_create_function(weight)
        })

    def register_predicates(self, name):
        mod = importlib.import_module(Provider.PRECOCATES_CLASS_PREFIX)
        predicate_create_function = getattr(mod, name)
        self.predicates_functions.append({
            'name': name,
            'predicate': predicate_create_function()
        })

    def schedule(self, app, nodes):
        _LOGGER.debug('Scheduling %s' % app.name)

        _LOGGER.debug('Computing predicates: ')
        for predicate_item in self.predicates_functions:
            _LOGGER.debug('predicate: ' + predicate_item['name'])
        filtered_nodes = self._find_nodes_that_fit(app, nodes)
        if len(filtered_nodes) is 0:
            _LOGGER.debug('There is no qualified nodes.')
            return False

        _LOGGER.debug('Prioritizing')
        for priority_item in self.priorities_functions:
            _LOGGER.debug('priority: ' + priority_item['name'])
        priority_queue = self._prioritize_nodes(app, filtered_nodes)
        result = self._select_host(app, priority_queue)
        return result

    def _find_nodes_that_fit(self, app, nodes):
        """Find the node that fits the application,
        this could be paralleled."""
        def filter_predicate(node):
            for predicate_item in self.predicates_functions:
                if not predicate_item['predicate'].predicate(app, node):
                    return False
            return True

        filtered_nodes = list(filter(filter_predicate, nodes))
        return filtered_nodes

    def _prioritize_nodes(self, app, filtered_nodes):
        """Calculate the scores of nodes, this could be paralleled since
        it uses map-reduce pattern."""
        results = [[] for k in range(len(self.priorities_functions))]

        # Map phase.
        priority_count = 0
        for priority_item in self.priorities_functions:
            priority_config = priority_item['priority']
            for node in filtered_nodes:
                results[priority_count].append(
                    priority_config.map(app, node))
            priority_count += 1

        # Reduce phase.
        priority_count = 0
        for priority_item in self.priorities_functions:
            priority_config = priority_item['priority']
            if priority_config.reduce is not None:
                priority_config.reduce(
                    app, filtered_nodes, results[priority_count])
            priority_count += 1

        result = list()
        for i in range(len(filtered_nodes)):
            result.append(priorities.ServerWithPriority(0, filtered_nodes[i]))
            priority_count = 0
            for priority_item in self.priorities_functions:
                result[i].priority = (result[i].priority +
                                      results[priority_count][i].priority *
                                      priority_item['priority'].weight)
                priority_count += 1

        result_priority = queue.PriorityQueue()
        for node in result:
            result_priority.put(node)
        return result_priority

    @staticmethod
    def _select_host(app, host_priority_queue):
        node = host_priority_queue.get().server
        _LOGGER.debug('Select the server ' + node.name + ' to run the app.')
        app.server = node.name
        return node.put_simple(app)
