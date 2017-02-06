"""Trace treadmill application events."""


import urllib.request
import urllib.parse
import urllib.error

import click

from treadmill import context
from treadmill import cli
from treadmill import restclient


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--api', required=False, help='API url to use.',
                  metavar='URL',
                  envvar='TREADMILL_STATEAPI')
    @click.option('--host', help='hostname.')
    @click.argument('service')
    def logs(api, host, service):
        """View application logs.
        """
        try:
            appname, uniq, logtype, service = service.split('/', 3)
        except ValueError:
            cli.bad_exit('Invalid service format: '
                         'expect <appname>/<uniq>/service/<servicename>')

        if bool(host) ^ bool(uniq != 'running'):
            cli.bad_exit('Usage: .../running/... and --host '
                         'are mutually exclusive.')

        apis = context.GLOBAL.state_api(api)

        if uniq == 'running':
            state_url = '/state?%s' % urllib.parse.urlencode(
                [('match', appname)]
            )
            where = restclient.get(apis, state_url).json()
            if not where:
                cli.bad_exit('%s not running.', appname)
            host = where[0]['host']
            if not host:
                cli.bad_exit('%s is pending.', appname)

        nodeinfo_url = '/endpoint/root.%s/tcp/nodeinfo' % host
        nodeinfo = restclient.get(apis, nodeinfo_url).json()
        if not nodeinfo:
            cli.bad_exit('Nodeinfo api not found: %s', host)

        nodeinfo_api = ['http://%s:%s' % (nodeinfo[0]['host'],
                                          nodeinfo[0]['port'])]
        logurl = '/app/%s/%s/%s/%s' % (
            urllib.parse.quote(appname),
            urllib.parse.quote(uniq),
            logtype,
            urllib.parse.quote(service))

        log = restclient.get(nodeinfo_api, logurl)
        print(log.text)

    return logs
