"""Trace treadmill application events."""


import sys

import logging
import os
import subprocess
import urllib

import click

from treadmill import context
from treadmill import cli
from treadmill import restclient
from treadmill.websocket import client as ws_client


_LOGGER = logging.getLogger(__name__)

if sys.platform == 'win32':
    _DEFAULT_SSH = 'putty.exe'
else:
    _DEFAULT_SSH = 'ssh'


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

    ssh = [ssh,
           '-o', 'UserKnownHostsFile=/dev/null',
           '-o', 'StrictHostKeyChecking=no',
           '-p', port, host] + command

    _LOGGER.debug('Starting ssh: %s', ssh)
    os.execvp(ssh[0], ssh)


def run_putty(host, port, sshcmd, command):
    """Runs standard ssh (non-windows)."""
    if not host or not port:
        return -2

    # Trick putty into storing ssh key automatically.
    plink = os.path.join(os.path.dirname(sshcmd), 'plink.exe')
    store_key_cmd = [plink, '-P', port,
                     '%s@%s' % (os.environ['USERNAME'], host), 'exit']

    _LOGGER.debug('Importing host key: %s', store_key_cmd)
    store_key_proc = subprocess.Popen(store_key_cmd,
                                      stdout=subprocess.PIPE,
                                      stdin=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
    out, err = store_key_proc.communicate(input='y\n\n\n\n\n\n\n\n\n')

    _LOGGER.debug('plink STDOUT: %s', out)
    _LOGGER.debug('plink STDERR: %s', err)

    if command:
        sshcmd = plink

    ssh = [sshcmd, '-P', port, '%s@%s' % (os.environ['USERNAME'], host)]
    if command:
        ssh.extend(command)

    _LOGGER.debug('Starting ssh: %s', ssh)
    try:
        if os.path.basename(sshcmd).lower() == 'putty.exe':
            os.execvp(ssh[0], ssh)
        else:
            subprocess.call(ssh)
    except KeyboardInterrupt:
        sys.exit(0)


def _wait_for_app(wsapi, ssh, app, command):
    """Use websockets to wait for the app to start"""
    def on_message(result):
        """Callback to process trace message."""
        host = result['host']
        port = result['port']
        run_ssh(host, port, ssh, list(command))
        return False

    def on_error(result):
        """Callback to process errors."""
        click.echo('Error: %s' % result['_error'], err=True)

    try:
        return ws_client.ws_loop(
            wsapi,
            {'topic': '/endpoints',
             'filter': app,
             'proto': 'tcp',
             'endpoint': 'ssh'},
            False,
            on_message,
            on_error
        )
    except ws_client.ConnectionError:
        cli.bad_exit('Could not connect to any Websocket APIs')


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--wsapi', required=False, help='WS API url to use.',
                  metavar='URL',
                  envvar='TREADMILL_WSAPI')
    @click.option('--api', required=False, help='API url to use.',
                  metavar='URL',
                  envvar='TREADMILL_STATEAPI')
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
    def ssh(wsapi, api, ssh, app, command, wait):
        """SSH into Treadmill container."""
        if ssh is None:
            ssh = _DEFAULT_SSH

        if wait:
            return _wait_for_app(wsapi, ssh, app, command)

        apis = context.GLOBAL.state_api(api)

        url = '/endpoint/{}/tcp/ssh'.format(urllib.parse.quote(app))

        response = restclient.get(apis, url)
        endpoints = response.json()
        _LOGGER.debug('endpoints: %r', endpoints)
        if not endpoints:
            cli.bad_exit('No ssh endpoint(s) found for %s', app)

        # Take the first one, if there are more than one, then this is
        # consistent with when 1 is returned.
        endpoint = endpoints[0]

        run_ssh(endpoint['host'], str(endpoint['port']), ssh, list(command))

    return ssh
