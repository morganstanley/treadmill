"""Yaml CLI formatter."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from treadmill import yamlwrapper as yaml


def format(obj):  # pylint: disable=W0622
    """Returns yaml representation of the object."""
    return yaml.dump(obj,
                     default_flow_style=False,
                     explicit_start=True,
                     explicit_end=True)
