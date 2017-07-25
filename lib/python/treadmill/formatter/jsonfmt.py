"""JSON CLI formatter."""

import json


def format(obj):  # pylint: disable=W0622
    """Output object as json."""
    return json.dumps(obj)
