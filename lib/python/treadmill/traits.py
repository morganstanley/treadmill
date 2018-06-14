"""Server traits.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from treadmill import plugin_manager
from treadmill import sysinfo

_LOGGER = logging.getLogger(__name__)


def format_traits(code, value):
    """Format traits as list of names.
    """
    result = []

    for trait in code:
        if value & code[trait]:
            result.append(trait)

    result.sort()
    return ','.join(result)


def detect(traits):
    """Detect traits usign plugins.
    """
    result = []

    for trait in traits:
        try:
            plugin = plugin_manager.load('treadmill.server.traits', trait)
            if plugin():
                result.append(trait)
        except Exception:  # pylint: disable=W0703
            _LOGGER.exception('Error processing trait plugin: %s', trait)

    return result


def create_code(traits):
    """Assign bits to list of traits.
    """
    if not traits:
        return {}

    result = {}
    code = 1

    for trait in traits:
        result[trait] = code
        code = code << 1

    return result


def encode(code, traits):
    """Code the list of traits into a number.
    """
    result = 0

    for trait in traits:
        if trait in code:
            result |= code[trait]
        else:
            _LOGGER.error('Unknown trait %s', trait)

    return result


def has_sse4():
    """Return true if current cpu has sse4 flag.
    """
    flags = sysinfo.cpu_flags()
    return 'sse4_1' in flags and 'sse4_2' in flags


def has_rdtscp():
    """Return true if current cpu has rdtscp flag.
    """
    flags = sysinfo.cpu_flags()
    return 'rdtscp' in flags
