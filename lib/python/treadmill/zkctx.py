"""Zookeeper context.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from treadmill import zkutils

_LOGGER = logging.getLogger(__name__)


def connect(zkurl):
    """Returns connection to Zookeeper.
    """
    return zkutils.connect(zkurl, listener=zkutils.exit_never)


def resolve(_ctx, attr):
    """Zookeeper context does not resolve any attributes.
    """
    raise KeyError(attr)


def init(_ctx):
    """Init context.
    """
    pass
