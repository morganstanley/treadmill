"""Forward tickets to the cell ticket locker.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import logging

import click
import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

from treadmill import cli
from treadmill import context
from treadmill import discovery


_LOGGER = logging.getLogger(__name__)

_REALM = 'is1.morgan'

_TKTFWD_RELEASE = os.path.join(
    'ms',
    'dist',
    'cloud',
    'PROJ',
    'treadmill-tktfwd',
    '1.9'
)

if os.name == 'nt':
    _TKTFWD_RELEASE = os.path.join(r'\\', _TKTFWD_RELEASE, 'msvc100', 'bin')
    _TKT_SEND = os.path.join(_TKTFWD_RELEASE, 'tkt-send.cmd')
    _TKT_SEND_V2 = os.path.join(_TKTFWD_RELEASE, 'tkt-send-v2.cmd')
else:
    _TKTFWD_RELEASE = os.path.join('/', _TKTFWD_RELEASE, 'bin')
    _TKT_SEND = os.path.join(_TKTFWD_RELEASE, 'tkt-send')
    _TKT_SEND_V2 = os.path.join(_TKTFWD_RELEASE, 'tkt-send-v2')


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--realm', help='Treadmill locker realm',
                  default=_REALM)
    @click.option('--legacy', help='Use legacy protocol.', is_flag=True,
                  default=False)
    def tktfwd(realm, legacy):
        """Forward prestashed tickets using legacy protocol."""
        zkclient = context.GLOBAL.zk.conn
        if legacy:
            app = '{}.tickets'.format(context.GLOBAL.zk.proid)
        else:
            app = '{}.tickets-v2'.format(context.GLOBAL.zk.proid)

        discovery_iter = discovery.iterator(zkclient, app, 'tickets', False)
        for (_app, hostport) in discovery_iter:
            host, port = hostport.split(':')

            if legacy:
                args = [_TKT_SEND,
                        hostport, 'host/%s@%s' % (host, realm)]
            else:

                args = [_TKT_SEND_V2,
                        '-h{}'.format(host),
                        '-p{}'.format(port)]

            try:
                _LOGGER.info('Forwarding tickets to: %s', hostport)
                subprocess.check_call(args)
            except subprocess.CalledProcessError as err:
                cli.bad_exit(str(err))
            except OSError as os_err:
                cli.bad_exit(str(os_err))

    return tktfwd
