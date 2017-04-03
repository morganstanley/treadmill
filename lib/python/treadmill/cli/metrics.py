"""Download treadmill app metrics given a pattern.

The files are downloaded for current directory, or it can be overwritten with
--outdir command line option.

"""
from __future__ import absolute_import

import logging
import os
import urllib

import click

from treadmill import cli
from treadmill import context
from treadmill import discovery
from treadmill import fs
from treadmill import restclient
from treadmill import rrdutils


_LOGGER = logging.getLogger(__name__)

# TODO: this list should be discoverable from the server rather than
#                hardcoded. GET /metrics/core should return this list.
_SYSTEM_SERVICES = [
    # Total metrics for non-treadmill (system), core services and all apps.
    'treadmill.system',
    'treadmill.core',
    'treadmill.apps',
]


def _get_nodeinfo_url(cell, api=None):
    """Get nodeinfo app url using discovery."""
    restapi = context.GLOBAL.admin_api(api)

    cell_obj = restclient.get(restapi, '/cell/%s' % cell).json()

    nodeinfo_app = '%s.%s' % (cell_obj['username'], 'nodeinfo')
    nodeinfo_iter = discovery.iterator(
        context.GLOBAL.zk.conn,
        nodeinfo_app,
        'http',
        watch=False
    )

    for (_app, hostport) in nodeinfo_iter:
        return 'http://%s' % hostport

    _LOGGER.critical('%s: %s is not running.', cell, nodeinfo_app)
    cli.bad_exit('%s: %s is not running.', cell, nodeinfo_app)


def _metrics_url(host, instance):
    """Return the url with which the application metrics can be retrieved."""
    return '/nodeinfo/{}/metrics/{}'.format(host, urllib.quote(instance))


def _rrdfile(outdir, *fname_parts):
    """Return the full path of the rrd file where the metrics will be saved.
    """
    return os.path.join(outdir, '-'.join(fname_parts) + '.rrd')


def _get_app_metrics(nodeinfo_url, outdir, appendpoint, hostport):
    """Retreives app metrics given discovery info."""
    fs.mkdir_safe(outdir)

    host, _port = hostport.split(':')
    instance, _proto, _endpoint = appendpoint.split(':')

    # assuming that only running application metrics should be retrieved
    _download_rrd(nodeinfo_url, _metrics_url(host, instance + '/running'),
                  _rrdfile(outdir, instance))


def _get_server_metrics(nodeinfo_url, outdir, server, services=None):
    """Get core services metrics."""
    fs.mkdir_safe(outdir)

    if not services:
        services = _SYSTEM_SERVICES

    for svc in services:
        _download_rrd(nodeinfo_url, _metrics_url(server, svc),
                      _rrdfile(outdir, server, svc))


def _download_rrd(nodeinfo_url, metrics_url, rrdfile):
    """Get rrd file and store in output directory."""
    _LOGGER.info('Download metrics from %s/%s', nodeinfo_url, metrics_url)
    try:
        resp = restclient.get(nodeinfo_url, metrics_url, stream=True)
        with open(rrdfile, 'w+b') as f:
            for chunk in resp.iter_content(chunk_size=128):
                f.write(chunk)

        rrdutils.gen_graph(rrdfile, rrdutils.RRDTOOL, show_mem_limit=False)
    except restclient.NotFoundError as err:
        _LOGGER.error('%s', err)
        cli.bad_exit('Metrics not found: %s', err)
    except rrdutils.RRDToolNotFoundError:
        cli.bad_exit('The rrdtool utility cannot be found in the PATH')


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--outdir', '-o', help='Output directory.',
                  type=click.Path(exists=True),
                  required=True)
    @click.option('--servers', type=cli.LIST,
                  help='List of servers to get core metrics')
    @click.option('--services', type=cli.LIST,
                  help='Subset of core services.')
    @click.argument('app', required=False)
    @click.option('--api', required=False, help='API url to use.',
                  envvar='TREADMILL_RESTAPI')
    def metrics(outdir, servers, services, app, api=None):
        """Retrieve node / app metrics."""
        cell = context.GLOBAL.cell
        nodeinfo_url = _get_nodeinfo_url(cell, api)

        if app:
            pattern = app.replace('%', '*')
            discovery_iter = discovery.iterator(
                context.GLOBAL.zk.conn,
                pattern,
                'ssh',
                watch=False
            )

            app_found = False
            for (appendpoint, hostport) in discovery_iter:
                _get_app_metrics(nodeinfo_url, outdir, appendpoint, hostport)
                app_found = True

            if not app_found:
                cli.bad_exit('Discovery found no trace of %s', app)

        for server in servers or []:
            _get_server_metrics(nodeinfo_url, outdir, server, services)

    return metrics
