"""Treadmill commaand line helpers.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


import codecs
import io
import json
import logging
import os

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
    import pkg_resources

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
    # Shortcut - check if logging already exists.
    logconf_path = os.path.join(
        os.environ.get('TREADMILL_APPROOT', ''),
        'logging',
        name
    )

    if os.path.exists(logconf_path):
        with io.open(logconf_path) as f:
            return json.loads(f.read())

    # load core logging config first
    conf = _load_logging_file(__name__, name)
    # get 'treadmill' default log configure
    default_conf = conf['loggers'].get(_package_root(__name__), {})

    # then load plugin component config
    import pkg_resources

    for plugin in plugin_manager.load_all(__name__):

        contents = pkg_resources.resource_listdir(__name__, '.')
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


def list_logging_conf():
    """List all defined logging configurations."""
    import pkg_resources

    configs = set()
    for plugin in plugin_manager.load_all(__name__):
        configs.update({
            cfg for cfg in pkg_resources.resource_listdir(__name__, '.')
            if cfg.endswith('.json')
        })

    return configs


def write_configs(logconf_dir):
    """Load and write logging configs."""
    for name in list_logging_conf():
        conf = load_logging_conf(name)
        with io.open(os.path.join(logconf_dir, name), 'w') as f:
            f.write(json.dumps(conf))
