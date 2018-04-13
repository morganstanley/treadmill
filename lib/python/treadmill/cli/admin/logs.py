"""Implementation of treadmill admin logs
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from six.moves import urllib_parse

from treadmill import cli
from treadmill import context
from treadmill import restclient
from treadmill import zknamespace as z


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--cell',
                  callback=cli.handle_context_opt,
                  envvar='TREADMILL_CELL',
                  expose_value=False,
                  required=True)
    @click.argument('app-or-svc')
    @click.option('--host',
                  help='Hostname where to look for the logs',
                  required=True)
    @click.option('--uniq',
                  help='The container uniq id',
                  required=False)
    @click.option('--service',
                  help='The name of the service for which the logs are '
                       'to be retreived',
                  required=False)
    def logs(app_or_svc, host, uniq, service):
        """View application's service logs."""
        try:
            app, uniq, logtype, logname = app_or_svc.split('/', 3)
        except ValueError:
            app, uniq, logtype, logname = app_or_svc, uniq, 'service', service

        if any(param is None for param in [app, uniq, logtype, logname]):
            cli.bad_exit('Incomplete parameter list')

        _host, port = _nodeinfo_endpoint(host)
        if not port:
            cli.bad_exit('Unable for fine nodeinfo endpoint.')

        api = 'http://{0}:{1}'.format(host, port)
        logurl = '/local-app/%s/%s/%s/%s' % (
            urllib_parse.quote(app),
            urllib_parse.quote(uniq),
            logtype,
            urllib_parse.quote(logname)
        )

        log = restclient.get(api, logurl)
        click.echo(log.text)

    return logs


def _nodeinfo_endpoint(host):
    """Find nodeinfo endpoint on host"""
    zkclient = context.GLOBAL.zk.conn
    nodeinfo_zk_path = '{}/{}'.format(z.ENDPOINTS, 'root')
    for node in zkclient.get_children(nodeinfo_zk_path):
        if 'nodeinfo' in node and host in node:
            data, _metadata = zkclient.get(
                '{}/{}'.format(nodeinfo_zk_path, node)
            )
            return data.decode().split(':')
    return None, None
