"""Zookeeper status interface."""

import socket
import logging

import click
import kazoo
import websocket as ws_client

from treadmill import cli
from treadmill import context
from treadmill import admin
from treadmill import restclient
from treadmill import zknamespace as z


_LOGGER = logging.getLogger(__name__)


def check(func, message):
    """Check function, output status message."""
    if func():
        _LOGGER.info('%s: ok', message)
    else:
        _LOGGER.error('%s: failed', message)


def _zkadmin(hostname, port, command):
    """Netcat."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((hostname, port))
    sock.sendall(command)
    sock.shutdown(socket.SHUT_WR)
    data = []
    while True:
        chunk = sock.recv(1024)
        if not chunk:
            break
        data.append(chunk)
    sock.close()
    return ''.join(data)


def check_zk():
    """Check Zookeeper ensemble health."""
    admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
    cell = admin_cell.get(context.GLOBAL.cell)
    success = True

    for master in cell['masters']:
        hostname = master['hostname']
        port = master['zk-client-port']
        try:
            zk_status = _zkadmin(hostname, port, 'ruok\n')
            _LOGGER.debug('%s:%s - %s', hostname, port, zk_status)
        except Exception as err:  # pylint: disable=W0703
            _LOGGER.error('%s:%s - %s', hostname, port, str(err))
            success = False

    return success


def _check_api(apis):
    """Check API status."""
    success = True
    if len(apis) < 2:
        _LOGGER.error('API is under capacity: expected 2, running: %s',
                      len(apis))
        success = False

    for api in apis:
        try:
            resp = restclient.get(api, '/', retries=0)
            _LOGGER.debug('%s - %r', api, resp.status_code)
        except restclient.MaxRequestRetriesError as err:
            _LOGGER.error('%s - %s', api, str(err))
            success = False

    return success


def check_cell_api():
    """Check API status."""
    try:
        return _check_api(context.GLOBAL.cell_api(None))
    except context.ContextError as err:
        _LOGGER.error('Unable to resolve cell api: %r', str(err))
        return False


def check_state_api():
    """Check API status."""
    try:
        return _check_api(context.GLOBAL.state_api(None))
    except context.ContextError as err:
        _LOGGER.error('Unable to resolve state api: %r', str(err))
        return False


def check_admin_api():
    """Check admin API."""
    try:
        return _check_api(context.GLOBAL.admin_api(None))
    except context.ContextError as err:
        _LOGGER.error('Unable to resolve admin api: %r', str(err))
        return False


def check_ws_api():
    """Check websocket API."""
    success = True
    try:
        for api in context.GLOBAL.ws_api(None):
            try:
                ws_client.create_connection(api)
                _LOGGER.debug('%s - ok.', api)
            except socket.error:
                _LOGGER.error('%s - failed.', api)
                success = False
    except context.ContextError as err:
        _LOGGER.error('Unable to resolve websocket api: %r', str(err))
        success = False

    return success


def check_blackouts():
    """Check blacked-out servers."""
    zkclient = context.GLOBAL.zk.conn
    try:
        blacked_out_nodes = zkclient.get_children(z.BLACKEDOUT_SERVERS)
        for server in blacked_out_nodes:
            _LOGGER.warn('Server blackedout: %s', server)
    except kazoo.client.NoNodeError:
        pass


def check_capacity():
    """Check cell capacity."""
    zkclient = context.GLOBAL.zk.conn
    configured = len(zkclient.get_children(z.SERVERS))
    blacked_out = len(zkclient.get_children(z.BLACKEDOUT_SERVERS))
    present = len(zkclient.get_children(z.SERVER_PRESENCE))

    _LOGGER.info('Server capacity - total: %s, blacked-out: %s, up: %s',
                 configured, blacked_out, present)

    check_blackouts()


def init():
    """Return top level command handler."""

    @click.command(name='ok')
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    def _ok():
        """Check status of Zookeeper ensemble."""
        log_level = logging.INFO
        if not logging.getLogger().isEnabledFor(log_level):
            logging.getLogger('treadmill').setLevel(log_level)
            logging.getLogger().setLevel(log_level)

        check(check_zk, 'Zookeeper ensemble')
        check_capacity()

        check(check_state_api, 'State api')
        check(check_cell_api, 'Cell api')
        check(check_admin_api, 'Admin api')
        check(check_ws_api, 'Websocket api')

    return _ok
