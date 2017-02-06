"""Trace treadmill application events."""


import sys
import signal

import logging
import os
import subprocess

import click

from treadmill import context
from treadmill import discovery
from treadmill import cli


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
        if os.path.basename(sshcmd).tolower() == 'putty.exe':
            os.execvp(ssh[0], ssh)
        else:
            subprocess.call(ssh)
    except KeyboardInterrupt:
        sys.exit(0)


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--ssh', help='SSH client to use.', type=click.File('rb'))
    @click.argument('app')
    @click.argument('command', nargs=-1)
    def ssh(ssh, app, command):
        """SSH into Treadmill container."""
        if ssh is None:
            ssh = _DEFAULT_SSH

        if app.find('#') == -1:
            # Instance is not specified, list matching and exit.
            raise click.BadParameter('Speficy full instance name: xxx#nnn')

        app_discovery = discovery.Discovery(context.GLOBAL.zk.conn, app, 'ssh')
        app_discovery.sync()

        # Restore default signal mask disabled by python spawning new thread
        # for Zk connection.
        #
        # TODO: should this be done as part of zkutils.connect?
        for sig in range(1, signal.NSIG):
            try:
                signal.signal(sig, signal.SIG_DFL)
            except RuntimeError:
                pass

        # TODO: not sure how to handle mutliple instances.
        for (app, hostport) in app_discovery.items():
            _LOGGER.info('%s :: %s', app, hostport)
            if hostport:
                host, port = hostport.split(':')
                run_ssh(host, port, ssh, list(command))

    return ssh
