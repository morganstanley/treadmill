"""JSON CLI formatter."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json


def format(obj):  # pylint: disable=W0622
    """Output object as json."""
    return json.dumps(obj)
