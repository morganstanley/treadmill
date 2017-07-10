from abc import ABCMeta, abstractmethod


class PriorityConfig(object):
    __metaclass__ = ABCMeta

    def __init__(self, weight):
        self.weight = weight

    @abstractmethod
    def map(self, app, node):
        """Map function must be defined."""

    @abstractmethod
    def reduce(self, app, nodes, result):
        """Reduce function is optional."""


class ServerWithPriority(object):
    def __init__(self, priority, server):
        self.priority = priority
        self.server = server
        return

    def __lt__(self, other):
        return self.priority < other.priority
