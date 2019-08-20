"""JSON CLI formatter."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json

from . import sanitize


class Default:
    """Default json formatter."""

    @staticmethod
    def format(obj):  # pylint: disable=W0622
        """Output object as indented json with removed nulls."""
        if isinstance(obj, dict):
            obj.pop('_id', None)

        return json.dumps(sanitize(obj), indent=2)


class Raw:
    """Raw json formatter."""

    @staticmethod
    def format(obj):  # pylint: disable=W0622
        """Output object as json."""
        if isinstance(obj, dict):
            obj.pop('_id', None)

        return json.dumps(obj)
