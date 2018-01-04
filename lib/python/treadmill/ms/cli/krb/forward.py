"""Forward Kerberos tickets to the cell ticket locker.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import logging
import os
import socket
import time

import click
import lockfile
import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

from treadmill import cli
from treadmill import context
from treadmill import dnsutils
from treadmill import exc
from treadmill import fs
from treadmill import restclient
from treadmill import utils

_LOGGER = logging.getLogger(__name__)

_RELEASE = '1.9'

_REALM = 'is1.morgan'

_HOME_DIR = os.path.expanduser('~')
_DEFAULT_WD = os.path.join(_HOME_DIR, '.treadmill-tkt-forward')

_ON_EXCEPTIONS = cli.handle_exceptions([
    (exc.InvalidInputError, None),
])

if os.name == 'nt':
    _DEFAULT_INTERVAL = '2h'
    _IS_LINUX = False
    _TKT_DIR = '\\\\' + os.path.join(
        'ms',
        'dist',
        'cloud',
        'PROJ',
        'treadmill-tktfwd',
        _RELEASE,
        'msvc100',
        'bin',
    )
    _TKT_INIT = os.path.join(_TKT_DIR, 'tkt-init.cmd')
    _TKT_SEND = os.path.join(_TKT_DIR, 'tkt-send.cmd')
    _TKT_SEND_V2 = os.path.join(_TKT_DIR, 'tkt-send-v2.cmd')
else:
    # Technically, else is not true
    _DEFAULT_INTERVAL = '1d'
    _IS_LINUX = True
    _TKT_DIR = '/' + os.path.join(
        'ms',
        'dist',
        'cloud',
        'PROJ',
        'treadmill-tktfwd',
        _RELEASE,
        'bin',
    )
    _TKT_SEND = os.path.join(_TKT_DIR, 'tkt-send')
    _TKT_SEND_V2 = os.path.join(_TKT_DIR, 'tkt-send-v2')


# TODO: implement logging to a file
def _win_daemonize(cells, realm, time_interval, _log=None):
    """Forward Kerberos tickets to the cell ticket locker."""
    from treadmill.ms import wx

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE

    def run_ticket_forwarding(per_cell_clbk=None, completed_clbk=None):
        """Run ticket forwarding comand"""
        try:
            _LOGGER.info('Fowarding tickets to %r', cells)
            _run_tkt_sender(
                cells, realm, stderr=subprocess.STDOUT,
                per_cell_clbk=per_cell_clbk,
                startupinfo=startupinfo,
                completed_clbk=completed_clbk,
            )
        except exc.InvalidInputError as err:
            cli.bad_exit(err.message)

    fs.mkdir_safe(_DEFAULT_WD)

    log_file = os.path.join(_DEFAULT_WD, 'forward.log')
    wx.run_ticket_forward_taskbar(
        log_filename=log_file,
        forward_tickets_clbk=run_ticket_forwarding,
        time_interval=time_interval
    )


def _linux_daemonize(cells, realm, detach, time_interval, log):
    """Forward Kerberos tickets to the cells ticket locker."""
    import daemon  # pylint: disable=C0413

    fs.mkdir_safe(_DEFAULT_WD)

    daemon_context = daemon.DaemonContext(
        working_directory=_DEFAULT_WD,
        umask=0o002,
        detach_process=detach,
        pidfile=lockfile.FileLock('{}/forward.pid'.format(_DEFAULT_WD))
    )

    if log:
        log_dir = os.path.dirname(log)
        fs.mkdir_safe(log_dir)
        fh = io.open(log, 'w')
        daemon_context.stdout = fh
        daemon_context.stderr = fh

    with daemon_context:
        while True:
            try:
                _LOGGER.info('Fowarding tickets to %r', cells)
                _run_tkt_sender(cells, realm)
                _LOGGER.info(
                    'Waiting %s seconds before refreshing again', time_interval
                )
                time.sleep(time_interval)
            except exc.InvalidInputError as err:
                cli.bad_exit(err.message)


def _daemonize(cells, realm, detach, refresh_interval, log):
    """Daemonize process into a loop, with refresh interval"""
    time_interval = utils.to_seconds(refresh_interval)

    if _IS_LINUX:
        _linux_daemonize(cells, realm, detach, time_interval, log)
    else:
        _win_daemonize(cells, realm, time_interval, log)


def _run(command, kwargs, ident, clbk):
    """Run command."""
    try:
        output = subprocess.check_output(command, **kwargs)
        success = True
    except subprocess.CalledProcessError as err:
        output = str(err)
        success = False

    if clbk:
        clbk(ident, output, success)


def _run_tkt_sender(cells, realm, stdout=None, stderr=None,
                    per_cell_clbk=None, startupinfo=None,
                    completed_clbk=None):
    """Actually run ticket sender"""
    dns_domain = context.GLOBAL.dns_domain

    if per_cell_clbk is None:
        def _default_cell_clbk(locker, output, status):
            """Default callback to print status of tkt forwarding."""
            print(
                'Forwarding tickets to locker {}: {}'.format(
                    locker,
                    'success' if status else 'failure'
                )
            )
            print(output)

        per_cell_clbk = _default_cell_clbk

    kwargs = {}
    if stdout:
        kwargs['stdout'] = stdout
    if stderr:
        kwargs['stderr'] = stderr
    if startupinfo:
        kwargs['startupinfo'] = startupinfo

    if os.name == 'nt':
        _run([_TKT_INIT], kwargs, 'init', per_cell_clbk)

    for cellname in cells:
        _LOGGER.info('Forwarding tickets to cell: %s', cellname)

        endpoints_v2 = _check_cell(cellname, 'tickets-v2', dns_domain)
        endpoints_v1 = _check_cell(cellname, 'tickets', dns_domain)

        if endpoints_v2:
            for idx, hostport in enumerate(endpoints_v2):
                host, port = hostport

                tkt_cmd = [
                    _TKT_SEND_V2,
                    '-h{}'.format(host),
                    '-p{}'.format(port),
                ]
                _run(tkt_cmd, kwargs,
                     '{0}/{1}'.format(cellname, idx),
                     per_cell_clbk)
        elif endpoints_v1:
            tkt_cmd = [
                _TKT_SEND,
                '--realm=%s' % realm,
                '--princ=host',
                '--timeout=5',
                '--endpoints=%s' % ','.join(['%s:%s' % (host, port)
                                             for host, port in endpoints_v1])
            ]
            _run(tkt_cmd, kwargs, cellname, per_cell_clbk)
        else:
            _LOGGER.warning('No ticket endpoints for cell: %s', cellname)

    if completed_clbk:
        _LOGGER.info('Calling completed_clbk: %r', completed_clbk)
        completed_clbk(cells)


def _get_cells():
    """Get all cell names"""
    restapi = context.GLOBAL.admin_api()
    cells = restclient.get(restapi, '/cell/').json()

    return [cell['_id'] for cell in cells]


def _check_cell(cellname, appname, dns_domain):
    """Return active endpoint for the locker given cell name."""
    srvrec = '_tickets._tcp.{}.{}.cell.{}'.format(appname,
                                                  cellname,
                                                  dns_domain)
    result = dnsutils.srv(srvrec, context.GLOBAL.dns_server)

    active = []
    for host, port, _, _ in result:
        sock = None
        try:
            sock = socket.create_connection((host, port), 1)
            active.append((host, port))
        except socket.error:
            _LOGGER.warning('Ticket endpoint [%s] is down: %s:%s',
                            cellname, host, port)
        finally:
            if sock:
                sock.close()

    active.sort()
    return active


def init():
    """Return top level command handler"""

    @click.command()
    @click.option('--cell', help='List of cells',
                  type=cli.LIST)
    @click.option('--realm', help='Ticket locker kerberos realm',
                  default=_REALM)
    @click.option('--detach', '-D', help='Detach process',
                  is_flag=True, default=False)
    @click.option('--continuous', '-C', help='Continuously forward tickets',
                  is_flag=True, default=False)
    @click.option('--refresh-interval',
                  help='How often to refresh your tickets',
                  default=_DEFAULT_INTERVAL)
    @click.option('--log', help='Log file location')
    @_ON_EXCEPTIONS
    def forward(cell, realm, detach, continuous,
                refresh_interval, log):
        """Forward Kerberos tickets to the cell ticket locker."""
        cells = cell
        if not cell:
            cells = _get_cells()

        if continuous:
            _daemonize(cells, realm, detach, refresh_interval, log)
            return

        _run_tkt_sender(cells, realm)

    return forward
