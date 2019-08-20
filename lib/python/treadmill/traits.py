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

# Invalid trait
INVALID = 'invalid'


def format_traits(code, value):
    """Format traits as list of names.
    """
    result = []

    for trait in code:
        if value & code[trait]:
            result.append(trait)

    result.sort()
    return ','.join(result)


def detect():
    """Detect traits usign plugins.
    """
    result = []

    plugins = plugin_manager.load_all('treadmill.server.traits')

    for plugin in plugins:
        try:
            result.extend(plugin())
        except Exception:  # pylint: disable=W0703
            _LOGGER.exception('Error processing plugin: %s', plugin)

    return result


def create_code(traits):
    """Assign bits to list of traits.
    """
    code = 1
    result = {INVALID: code}

    if not traits:
        return result

    for trait in traits:
        code = code << 1
        result[trait] = code

    return result


def encode(code, traits, use_invalid=False, add_new=False):
    """Code the list of traits into a number.
    """
    result = 0
    next_code = max(code.values(), default=1)

    for trait in traits:
        if trait in code:
            result |= code[trait]
        elif add_new:
            next_code = next_code << 1
            code[trait] = next_code
            result |= code[trait]
        else:
            _LOGGER.error('Unknown trait %s', trait)
            if use_invalid:
                result |= code[INVALID]

    return result, code


def detect_cpuflags():
    """Return traits describing cpu capabilities.
    """
    result = []
    flags = sysinfo.cpu_flags()

    if 'sse4_1' in flags and 'sse4_2' in flags:
        result.append('sse4')

    if 'rdtscp' in flags:
        result.append('rdtscp')

    return result


def detect_hwmodel():
    """Return trait corresponding to hw model.
    """
    model = sysinfo.hwmodel()
    if model:
        return [model.replace(' ', '_')]
    else:
        return []
