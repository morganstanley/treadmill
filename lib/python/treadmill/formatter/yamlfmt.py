"""Yaml CLI formatter."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from treadmill import yamlwrapper as yaml
from . import sanitize


class Default:
    """Default YAML formatter."""

    @staticmethod
    def format(obj):  # pylint: disable=W0622
        """Returns yaml representation of the object with stripped nulls."""
        if isinstance(obj, dict):
            obj.pop('_id', None)

        return yaml.dump(sanitize(obj),
                         default_flow_style=False,
                         explicit_start=True,
                         explicit_end=True)


class Raw:
    """Raw YAML formatter."""

    @staticmethod
    def format(obj):  # pylint: disable=W0622
        """Returns raw yaml representation of the object."""
        if isinstance(obj, dict):
            obj.pop('_id', None)

        return yaml.dump(obj,
                         default_flow_style=False,
                         explicit_start=True,
                         explicit_end=True)
