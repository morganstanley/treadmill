"""Treadmill commaand line helpers.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


import codecs
import json
import logging

import pkg_resources

from treadmill import plugin_manager


def set_log_level(log_level):
    """Set loglevel for all treadmill modules
    """
    # pylint: disable=consider-iterating-dictionary
    # yes, we need to iterate keys
    logger_keys = [
        lk for lk in logging.Logger.manager.loggerDict.keys()
        if '.' not in lk and lk[:9] == 'treadmill'
    ]

    logging.getLogger().setLevel(log_level)
    for logger_key in logger_keys:
        logging.getLogger(logger_key).setLevel(log_level)


def _load_logging_file(plugin_name, name):
    """Load logging config json file from treadmill_xx/logging/xxx.json
    """
    utf8_reader = codecs.getreader('utf8')
    log_conf_file = utf8_reader(
        pkg_resources.resource_stream(plugin_name, name)
    )
    return json.load(log_conf_file)


def _package_root(name):
    """Convert treadmill.logging.xxx => treadmill
    """
    return name.split('.', 1)[0]


def load_logging_conf(name):
    """load plugin log conf from various modules
    """
    # load core logging config first
    conf = _load_logging_file(__name__, name)
    # get 'treadmill' default log configure
    default_conf = conf['loggers'].get(_package_root(__name__), {})

    # then load plugin component config
    for plugin in plugin_manager.load_all(__name__):
        try:
            plugin_conf = _load_logging_file(plugin.__name__, name)

            # TODO: deep merge conf
            conf['loggers'].update(plugin_conf.get('loggers', {}))
        except FileNotFoundError as _e:
            # it is possible for module to be lack of specific log file
            # e.g. some module does not have daemon logging configuration
            # we use default configure for it
            plugin_package_root_name = _package_root(plugin.__name__)
            conf['loggers'][plugin_package_root_name] = default_conf

    return conf
