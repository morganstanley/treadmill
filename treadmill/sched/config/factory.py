import logging
import json
import sys

from .. import algoprovider

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

class Config(object):
    def __init__(self, algorithm_provider):
        self.algorithm_provider = algorithm_provider


class ConfigFactory(object):
    __slots__ = (
        'algorithm_provider',
    )

    def __init__(self):
        self.algorithm_provider = algoprovider.Provider()

    def read_config_from_file(self, file):
        PRIDICATES_NAME = 'predicates'
        PRIOTITIES_NAME = 'priorities'
        CONFIG_NAME = 'name'
        PRIORITY_WEIGHT = 'weight'

        with open(file, 'r') as config_file:
            json_str = config_file.read()
            config = json.loads(json_str)
            # TODO: `is not None` does not work to check if the ket exists.
            if config[PRIDICATES_NAME] is not None:
                for predicate in config[PRIDICATES_NAME]:
                    self.algorithm_provider.register_predicates(predicate[CONFIG_NAME])
            else:
                _LOGGER.fatal("There is no config about predicates defined!")

            if config[PRIOTITIES_NAME] is not None:
                for priority in config[PRIOTITIES_NAME]:
                    self.algorithm_provider.register_priorities(priority[CONFIG_NAME], priority[PRIORITY_WEIGHT])
            else:
                _LOGGER.fatal("There is no config about priorities defined!")

        return self

    def with_default_algorithm_provider(self):
        self.algorithm_provider = algoprovider.default_provider()
        return self

    def build(self):
        return Config(self.algorithm_provider)
