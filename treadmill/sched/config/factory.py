import logging
import json
import sys

from ..algoprovider import provider

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


class Config(object):
    def __init__(self, algorithm_provider):
        self.algorithm_provider = algorithm_provider


class ConfigFactory(object):
    __slots__ = (
        'algorithm_provider',
    )

    PREDICATES_NAME = 'predicates'
    PRIORITIES_NAME = 'priorities'
    CONFIG_NAME = 'name'
    PRIORITY_WEIGHT = 'weight'

    def __init__(self):
        self.algorithm_provider = provider.Provider()

    def read_config_from_file(self, filename):
        """Read config from the given file."""
        _LOGGER.debug('Read config from the given file ' + filename)
        with open(filename, 'r') as config_file:
            json_str = config_file.read()
            config = json.loads(json_str)

            if self.PREDICATES_NAME in config:
                for predicate in config[self.PREDICATES_NAME]:
                    if self.CONFIG_NAME in predicate:
                        _LOGGER.debug('Add ' + predicate[self.CONFIG_NAME] +
                                      ' to scheduler provider.')
                        self.algorithm_provider.register_predicates(
                            predicate[self.CONFIG_NAME])
                    else:
                        _LOGGER.fatal("Predicate should "
                                      "have a name defined in config file.")
            else:
                _LOGGER.fatal("There is no config about predicates defined!")

            if self.PRIORITIES_NAME in config:
                for priority in config[self.PRIORITIES_NAME]:
                    if self.CONFIG_NAME in priority and \
                       self.PRIORITY_WEIGHT in priority:
                        _LOGGER.debug('Add ' + priority[self.CONFIG_NAME] +
                                      ' to scheduler provider.')
                        self.algorithm_provider.register_priorities(
                            priority[self.CONFIG_NAME],
                            priority[self.PRIORITY_WEIGHT])
                    else:
                        _LOGGER.fatal("Predicate should "
                                      "have a name and weight "
                                      "defined in config file.")
            else:
                _LOGGER.fatal("There is no config about priorities defined!")

        return self

    def build(self):
        return Config(self.algorithm_provider)
