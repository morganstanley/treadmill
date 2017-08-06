from abc import ABCMeta, abstractmethod


class PredicateConfig(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def predicate(self, app, node):
        """Run predicate method."""
