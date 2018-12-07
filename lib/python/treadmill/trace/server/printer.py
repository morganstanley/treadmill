"""Server trace printer.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from treadmill import utils

from . import events


class ServerTracePrinter(events.ServerTraceEventHandler):
    """Output out trace events.
    """

    def on_server_state(self, when, servername, state):
        """Invoked when server state changes.
        """
        print('%s - %s %s' % (
            utils.strftime_utc(when), servername, state))

    def on_server_blackout(self, when, servername):
        """Invoked when server is blackedout.
        """
        print('%s - %s blackout' % (
            utils.strftime_utc(when), servername))

    def on_server_blackout_cleared(self, when, servername):
        """Invoked when server blackout is cleared.
        """
        print('%s - %s cleared' % (
            utils.strftime_utc(when), servername))
