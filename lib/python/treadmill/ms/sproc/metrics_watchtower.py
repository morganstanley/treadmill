"""Connect cgroup info service by unixsocket
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click

from six.moves import urllib_parse

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import metrics_watchtower

#: Metric collection interval (every X seconds)
_METRIC_STEP_SEC_MIN = 60
_METRIC_STEP_SEC_MAX = 300

_LOGGER = logging.getLogger(__name__)


def init():
    """Main command handler.
    """
    @click.command()
    @click.option('--step', '-s',
                  type=click.IntRange(_METRIC_STEP_SEC_MIN,
                                      _METRIC_STEP_SEC_MAX),
                  default=_METRIC_STEP_SEC_MIN,
                  help='Metrics collection frequency (sec)')
    @click.option('--socket', help='unix-socket of cgroup API service',
                  required=True)
    @click.option('--host', default='localhost',
                  help='Watchtower collecotor host address')
    @click.option('--port', type=int, default=13684,
                  help='Watchtower collecotor port')
    @click.option('--service/--no-service',
                  is_flag=True, default=False,
                  help='Also forward Treadmill service metrics')
    def metrics_forwarder(step, socket, host, port, service):
        """read metrics from unixsocket and send to WT
        """
        remote = 'http+unix://{}'.format(urllib_parse.quote_plus(socket))
        _LOGGER.info('remote cgroup API address %s', remote)

        daemon = metrics_watchtower.MetricsForwarder(host, port, remote)
        daemon.run(step, service)

        # Gracefull shutdown.
        _LOGGER.info('service shutdown.')

    return metrics_forwarder
