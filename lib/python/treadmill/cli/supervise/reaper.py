"""Runs healthcheck and reaps instances that are unhealthy.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import logging
import os
import time

import click
import six

from six.moves import urllib_parse

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=E0401
else:
    import subprocess  # pylint: disable=wrong-import-order

from treadmill import cli
from treadmill import context
from treadmill import restclient
from treadmill import utils


_LOGGER = logging.getLogger(__name__)

_DEFAULT_INTERVAL = '1m'

_CLOSE_FDS = os.name != 'nt'


def _health_check(pattern, proto, endpoint, command):
    """Invoke instance health check."""
    stateapi = context.GLOBAL.state_api()
    stateurl = '/endpoint/%s/%s/%s' % (urllib_parse.quote(pattern),
                                       proto,
                                       endpoint)

    response = restclient.get(stateapi, stateurl)
    lines = [
        '%s %s' % (end['name'], '%s:%s' % (end['host'], end['port']))
        for end in response.json()
    ]
    cmd_input = '\n'.join(lines)
    bad = []
    try:
        proc = subprocess.Popen(
            command,
            close_fds=_CLOSE_FDS, shell=False,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        (out, _err) = proc.communicate(cmd_input.encode())

        retcode = proc.returncode
        if proc.returncode == 0:
            for instance in out.decode().splitlines():
                _LOGGER.info('not ok: %s', instance)
                bad.append(instance)
        else:
            _LOGGER.warning('Health check ignored. %r, rc: %s.',
                            command, retcode)
    except Exception:  # pylint: disable=W0703
        _LOGGER.exception('Error invoking: %r', command)

    return bad


def _reap(bad):
    """Delete instances that did not path health check."""
    if not bad:
        return []

    cellapi = context.GLOBAL.cell_api()
    try:
        for instance in bad:
            _LOGGER.info('Delete: %s', instance)

        restclient.post(cellapi, '/instance/_bulk/delete',
                        payload=dict(instances=bad))
        return bad
    except Exception:  # pylint: disable=W0703
        _LOGGER.exception('Error reaping: %r', bad)
        return []


def init():
    """Return top level command handler"""

    @click.command()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--once', help='Run once.', is_flag=True, default=False)
    @click.option('--interval', help='Wait interval between checks.',
                  default=_DEFAULT_INTERVAL)
    @click.option('--threshold', help='Number of failed checks before reap.',
                  default=1)
    @click.option('--proto', help='Endpoint protocol.', default='tcp',
                  type=click.Choice(['tcp', 'udp']))
    @click.argument('pattern')
    @click.argument('endpoint')
    @click.argument('command', nargs=-1)
    def reaper(once, interval, threshold, proto, pattern, endpoint, command):
        """Removes unhealthy instances of the app.

        The health check script reads from STDIN and prints to STDOUT.

        The input it list of instance host:port, similar to discovery.

        Output - list of instances that did not pass health check.

        For example, specifying awk '{print $1}' as COMMAND will remove all
        instances.
        """
        command = list(command)

        failed = collections.Counter()
        while True:
            failed.update(_health_check(pattern, proto, endpoint, command))
            for instance, count in six.iteritems(failed):
                _LOGGER.info('Failed: %s, count: %s', instance, count)

            reaped = _reap(
                [
                    instance
                    for instance, count in six.iteritems(failed)
                    if count > threshold
                ]
            )

            for instance in reaped:
                del failed[instance]

            if once:
                break

            time.sleep(utils.to_seconds(interval))

    return reaper
