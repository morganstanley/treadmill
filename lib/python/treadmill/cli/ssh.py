"""Trace treadmill application events.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import shutil
import socket
import subprocess
import sys

import click

import gevent
from gevent import queue as g_queue

import six
from six.moves import urllib_parse

from treadmill import context
from treadmill import cli
from treadmill import restclient
from treadmill import utils
from treadmill.websocket import client as ws_client


_LOGGER = logging.getLogger(__name__)

if sys.platform == 'win32':
    _DEFAULT_SSH = 'putty.exe'
else:
    _DEFAULT_SSH = 'ssh'


def _connect(host, port):
    """Check host:port is up."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)

    try:
        sock.connect((host, int(port)))
        sock.close()
        return True
    except socket.error:
        return False


def _check_handle(handle):
    """Checks if provided file handle is valid."""
    return handle is not None and handle.fileno() >= 0


def run_ssh(host, port, ssh, command):
    """Runs ssh."""
    if sys.platform == 'win32':
        run_putty(host, port, ssh, command)
    else:
        run_unix(host, port, ssh, command)


def run_unix(host, port, ssh, command):
    """Runs standard ssh (non-windows)."""
    if not host or not port:
        return -2

    if not shutil.which(ssh):
        cli.bad_exit('{} cannot be found in the PATH'.format(ssh))

    ssh = [ssh,
           '-o', 'UserKnownHostsFile=/dev/null',
           '-o', 'StrictHostKeyChecking=no',
           '-p', port, host] + command

    _LOGGER.debug('Starting ssh: %s', ssh)
    return utils.sane_execvp(ssh[0], ssh)


def run_putty(host, port, sshcmd, command):
    """Runs plink/putty (windows)."""
    if not host or not port:
        return -2

    # Trick putty into storing ssh key automatically.
    plink = os.path.join(os.path.dirname(sshcmd), 'plink.exe')

    if not shutil.which(plink):
        cli.bad_exit('{} cannot be found in the PATH'.format(plink))

    store_key_cmd = [plink, '-P', port,
                     '%s@%s' % (os.environ['USERNAME'], host), 'exit']

    _LOGGER.debug('Importing host key: %s', store_key_cmd)
    store_key_proc = subprocess.Popen(store_key_cmd,
                                      stdout=subprocess.PIPE,
                                      stdin=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
    out, err = store_key_proc.communicate(input='y\n\n\n\n\n\n\n\n\n'.encode())

    _LOGGER.debug('plink STDOUT: %s', out)
    _LOGGER.debug('plink STDERR: %s', err)

    if command:
        sshcmd = plink

    ssh = [sshcmd, '-P', port, '%s@%s' % (os.environ['USERNAME'], host)]
    if command:
        ssh.extend(command)

    devnull = {}

    def _get_devnull():
        """Gets handle to the null device."""
        if not devnull:
            devnull['fd'] = os.open(os.devnull, os.O_RDWR)
        return devnull['fd']

    if not shutil.which(sshcmd):
        cli.bad_exit('{} cannot be found in the PATH'.format(sshcmd))

    _LOGGER.debug('Starting ssh: %s', ssh)
    try:
        if os.path.basename(sshcmd).lower() == 'putty.exe':
            utils.sane_execvp(ssh[0], ssh)
        else:
            # Call plink. Redirect to devnull if std streams are empty/invalid.
            subprocess.call(
                ssh,
                stdin=None if _check_handle(sys.stdin) else _get_devnull(),
                stdout=None if _check_handle(sys.stdout) else _get_devnull(),
                stderr=None if _check_handle(sys.stderr) else _get_devnull()
            )
    except KeyboardInterrupt:
        sys.exit(0)
    finally:
        if devnull:
            os.close(devnull['fd'])


def _wait_for_ssh(queue, ssh, command, timeout=1, attempts=40):
    """Wait until a successful connection to the ssh endpoint can be made."""
    try:
        host, port = queue.get(timeout=timeout * attempts)
    except g_queue.Empty:
        cli.bad_exit('No SSH endpoint found.')

    for _ in six.moves.range(attempts):
        _LOGGER.debug('Checking SSH endpoint %s:%s', host, port)
        if _connect(host, port):
            run_ssh(host, port, ssh, list(command))
            break  # if run_ssh doesn't end with os.execvp()...

        try:
            host, port = queue.get(timeout=timeout)
            queue.task_done()
        except g_queue.Empty:
            pass

    # Either all the connection attempts failed or we're after run_ssh
    # (not resulting in os.execvp) so let's "clear the queue" so the thread
    # can join
    queue.task_done()


def _wait_for_app(ssh, app, command, queue=None):
    """Use websockets to wait for the app to start"""
    # JoinableQueue is filled with a dummy item otherwise queue.join() unblocks
    # immediately wo/ actually letting the ws_loop and _wait_for_ssh to run.
    queue = queue or g_queue.JoinableQueue(items=[('dummy.host', 1234)])

    def on_message(result, queue=queue):
        """Callback to process trace message."""
        _LOGGER.debug('Endpoint trase msg: %r', result)
        queue.put((result['host'], result['port']))
        return False

    def on_error(result):
        """Callback to process errors."""
        click.echo('Error: %s' % result['_error'], err=True)

    try:
        gevent.spawn(_wait_for_ssh, queue, ssh, command)
        gevent.spawn(ws_client.ws_loop,
                     context.GLOBAL.ws_api(),
                     {'topic': '/endpoints',
                      'filter': app,
                      'proto': 'tcp',
                      'endpoint': 'ssh'},
                     False,
                     on_message,
                     on_error)

        queue.join()

    except ws_client.WSConnectionError:
        cli.bad_exit('Could not connect to any Websocket APIs')


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--wait', help='Wait until the app starts up',
                  is_flag=True, default=False)
    @click.option('--ssh', help='SSH client to use.',
                  type=click.Path(exists=True, readable=True))
    @click.argument('app')
    @click.argument('command', nargs=-1)
    def ssh(ssh, app, command, wait):
        """SSH into Treadmill container."""
        if ssh is None:
            ssh = _DEFAULT_SSH

        if wait:
            _wait_for_app(ssh, app, command)

        else:
            apis = context.GLOBAL.state_api()

            url = '/endpoint/{}/tcp/ssh'.format(urllib_parse.quote(app))

            response = restclient.get(apis, url)
            endpoints = response.json()
            _LOGGER.debug('endpoints: %r', endpoints)
            if not endpoints:
                cli.bad_exit('No ssh endpoint(s) found for %s', app)

            # Take the first one, if there are more than one, then this is
            # consistent with when 1 is returned.
            endpoint = endpoints[0]
            run_ssh(
                endpoint['host'],
                str(endpoint['port']), ssh, list(command)
            )

    return ssh
