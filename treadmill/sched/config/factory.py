import logging
import json
import sys

from ..algoprovider import provider, default

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

    def read_config_from_file(self, file):
        with open(file, 'r') as config_file:
            json_str = config_file.read()
            config = json.loads(json_str)
            # TODO: `is not None` does not work to check if the ket exists.
            if config[self.PREDICATES_NAME] is not None:
                for predicate in config[self.PREDICATES_NAME]:
                    self.algorithm_provider.register_predicates(
                        predicate[self.CONFIG_NAME])
            else:
                _LOGGER.fatal("There is no config about predicates defined!")

            if config[self.PRIORITIES_NAME] is not None:
                for priority in config[self.PRIORITIES_NAME]:
                    self.algorithm_provider.register_priorities(
                        priority[self.CONFIG_NAME], priority[self.PRIORITY_WEIGHT])
            else:
                _LOGGER.fatal("There is no config about priorities defined!")

        return self

    def with_default_provider(self):
        self.algorithm_provider = default.default_provider()
        return self

    def build(self):
        return Config(self.algorithm_provider)
