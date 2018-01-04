"""Trace treadmill application events.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click
from six.moves import urllib_parse

from treadmill import cli
from treadmill import context
from treadmill import restclient
from treadmill import utils

_LOGGER = logging.getLogger(__name__)

# This whole module is MS specific.
_DEFAULT_NETADMIN = '/ms/dist/appmw/PROJ/netadmin/static/bin/netAdminCmd'


def run_netadmin(hostport, netadmin, kerberos, command):
    """Runs netadmin."""
    if not hostport:
        return -2

    cmd = [netadmin]
    if kerberos:
        cmd.append('-k')
    cmd += [hostport] + command

    _LOGGER.debug('Starting netadmin: %s', cmd)
    utils.sane_execvp(cmd[0], cmd)


def init():
    """Return top level command handler."""

    @click.command(name='netadmin')
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--api', required=False, help='API url to use.',
                  metavar='URL',
                  envvar='TREADMILL_STATEAPI')
    @click.option('--netadmin', help='netadmin client to use.',
                  type=click.Path(exists=True, readable=True))
    @click.option('-k', '--kerberos', help='Create kerberos connection',
                  is_flag=True, default=False)
    @click.argument('app')
    @click.argument('command', nargs=-1)
    def netadmin_cmd(api, netadmin, kerberos, app, command):
        """Run netadmin command."""
        if netadmin is None:
            netadmin = _DEFAULT_NETADMIN

        if app.find('#') == -1:
            # Instance is not specified, list matching and exit.
            raise click.BadParameter('Speficy full instance name: xxx#nnn')

        apis = context.GLOBAL.state_api(api)

        url = '/endpoint/{}/tcp/netadmin'.format(urllib_parse.quote(app))

        response = restclient.get(apis, url)
        endpoints = response.json()
        _LOGGER.debug('endpoints: %r', endpoints)
        if not endpoints:
            cli.bad_exit('No netadmin endpoint(s) found for %s', app)

        # Take the first one, if there are more than one, then this is
        # consistent with when 1 is returned.
        endpoint = endpoints[0]

        hostport = ':'.join((endpoint['host'], str(endpoint['port'])))
        run_netadmin(hostport, netadmin, kerberos, list(command))

    return netadmin_cmd
