"""Download treadmill app metrics given a pattern or exact app name.

The files are downloaded to the directory specified by the --outdir command
line option.
"""

import functools
import logging
import os
import urllib.request
import urllib.parse
import urllib.error

import click

from treadmill import cli
from treadmill import context
from treadmill import fs
from treadmill import restclient
from treadmill import rrdutils
from treadmill.websocket import client as wsc

_LOGGER = logging.getLogger(__name__)

# TODO: this list should be discoverable from the server rather than
#                hardcoded. GET /metrics/core should return this list.
_SYSTEM_SERVICES = [
    # Total metrics for non-treadmill (system), core services and all apps.
    'treadmill.system',
    'treadmill.core',
    'treadmill.apps',
]


def _find_nodeinfo_endpoints(api=None):
    """Return all the nodeinfo endpoints in the cell.

    The return value is a dict with host-endpoint assigments as key-value
    pairs.
    """
    endpoints = _get_endpoints(api)
    return _endpoints_by_hosts(endpoints)


def _get_endpoints(api=None):
    """Return all the nodeinfo endpoints for the given cell."""
    apis = context.GLOBAL.state_api(api)

    url = '/endpoint/{}/tcp/nodeinfo'.format(urllib.parse.quote('root.*'))
    response = restclient.get(apis, url)

    endpoints = [{
        'name': end['name'],
        'proto': end['proto'],
        'endpoint': end['endpoint'],
        'hostport': '{0}:{1}'.format(end['host'], end['port'])
    } for end in response.json()]

    if not endpoints:
        cli.bad_exit("Nodeinfo API couldn't be found")

    return endpoints


def _endpoints_by_hosts(endpoints):
    """Return a dict consisting of the host-endpoint pairs as key-values."""
    rv = {}
    for ep in endpoints:
        host, _ = ep['hostport'].split(':')
        rv[host] = ep

    return rv


def _get_endpoint_for_host(endpoints, host):
    """Return the nodeinfo endpoint running on the host in parameter."""
    try:
        rv = endpoints[host]
    except KeyError:
        cli.bad_exit('Nodeinfo endpoint not found on %s', host)

    return rv


def _instance_to_host_uniq(in_=None, out_=None, uniq=None):
    """Update out_ so it contains 'instance: {host, uniq}' as key: value pairs.
    """
    if 'event' not in in_ or not in_['event']:
        return True

    if 'uniqueid' not in in_['event'] or in_['event']['uniqueid'] != uniq:
        return True

    out_[in_['event']['instanceid']] = in_['event']['source']
    return True


def _find_uniq_instance(instance, uniq, ws_api=None):
    """Find out where the given instance/uniq is/has been running."""
    rv = {}
    message = {'topic': '/trace', 'filter': instance, 'snapshot': True}
    on_message = functools.partial(_instance_to_host_uniq, out_=rv, uniq=uniq)

    wsc.ws_loop(ws_api, message, True, on_message)

    return rv


def _instance_to_host(in_=None, out_=None):
    """Update out_ so it contains 'instance: host' as key: value pairs."""
    if 'host' not in in_:
        return True

    out_[in_['name']] = in_['host']
    return True


def _find_running_instance(app, ws_api=None):
    """Find the instance name(s) and host(s) corresponding to the application.
    """
    rv = {}
    message = {'topic': '/endpoints',
               'filter': app,
               'proto': 'tcp',
               'endpoint': 'ssh',
               'snapshot': True}

    on_message = functools.partial(_instance_to_host, out_=rv)

    wsc.ws_loop(ws_api, message, True, on_message)

    return rv


def _metrics_url(*name_parts):
    """Return the url with which the application metrics can be retrieved."""
    return '/metrics/{}'.format(urllib.parse.quote('/'.join(name_parts)))


def _rrdfile(outdir, *fname_parts):
    """Return the full path of the rrd file where the metrics will be saved.
    """
    return os.path.join(outdir, '-'.join(fname_parts) + '.rrd')


def _get_app_rsrc(instance, admin_api=None, cell_api=None):
    """Return the application's reserved resources from the manifest."""
    try:
        mf = restclient.get(context.GLOBAL.cell_api(cell_api),
                            '/instance/%s' % urllib.quote(instance)).json()
    except restclient.NotFoundError:
        mf = restclient.get(context.GLOBAL.admin_api(admin_api),
                            '/app/%s' % instance).json()

    return {rsrc: mf[rsrc] for rsrc in ('cpu', 'disk', 'memory')
            if rsrc in mf}


def _get_app_metrics(endpoint, instance, uniq='running', outdir=None,
                     cell_api=None):
    """Retreives app metrics."""
    fs.mkdir_safe(outdir)
    reserved_rsrc = _get_app_rsrc(instance, cell_api)

    api = 'http://{}'.format(endpoint['hostport'])
    _download_rrd(api, _metrics_url(instance, uniq),
                  _rrdfile(outdir, instance, uniq), reserved_rsrc)


def _get_server_metrics(endpoint, server, services=None, outdir=None):
    """Get core services metrics."""
    fs.mkdir_safe(outdir)

    api = 'http://{}'.format(endpoint['hostport'])

    if not services:
        services = _SYSTEM_SERVICES

    for svc in services:
        _download_rrd(api, _metrics_url(svc), _rrdfile(outdir, server, svc))


def _download_rrd(nodeinfo_url, metrics_url, rrdfile, reserved_rsrc=None):
    """Get rrd file and store in output directory."""
    _LOGGER.info('Download metrics from %s/%s', nodeinfo_url, metrics_url)
    try:
        resp = restclient.get(nodeinfo_url, metrics_url, stream=True)
        with open(rrdfile, 'w+b') as f:
            for chunk in resp.iter_content(chunk_size=128):
                f.write(chunk)

        rrdutils.gen_graph(rrdfile, rrdutils.RRDTOOL,
                           reserved_rsrc=reserved_rsrc)
    except restclient.NotFoundError as err:
        _LOGGER.error('%s', err)
        cli.bad_exit('Metrics not found: %s', err)
    except rrdutils.RRDToolNotFoundError:
        cli.bad_exit('The rrdtool utility cannot be found in the PATH')


def init():
    """Top level command handler."""

    ctx = {}

    @click.group()
    @click.option('--cell-api',
                  envvar='TREADMILL_CELLAPI',
                  help='Cell API url to use.',
                  required=False)
    @click.option('--api',
                  envvar='TREADMILL_STATEAPI',
                  help='State API url to use.',
                  required=False)
    @click.option('--cell',
                  callback=cli.handle_context_opt,
                  envvar='TREADMILL_CELL',
                  expose_value=False,
                  required=True)
    @click.option('--outdir',
                  '-o',
                  help='Output directory.',
                  required=True,
                  type=click.Path(exists=True))
    @click.option('--ws-api', help='Websocket API url to use.', required=False)
    def metrics(cell_api, api, outdir, ws_api):
        """Retrieve node / app metrics."""
        ctx['cell_api'] = cell_api
        ctx['nodeinf_eps'] = _find_nodeinfo_endpoints(api)
        ctx['outdir'] = outdir
        ctx['ws_api'] = ws_api

    @metrics.command()
    @cli.ON_REST_EXCEPTIONS
    @click.argument('app_pattern')
    def running(app_pattern):
        """Get the metrics of running instances."""
        instances = _find_running_instance(app_pattern, ctx['ws_api'])
        if not instances:
            cli.bad_exit('No running instance matched the pattern.')

        _LOGGER.debug('Found instance(s): %s', instances)

        for inst, host in instances.items():
            endpoint = _get_endpoint_for_host(ctx['nodeinf_eps'], host)

            _get_app_metrics(endpoint, inst, outdir=ctx['outdir'],
                             cell_api=ctx['cell_api'])

    @metrics.command()
    @cli.ON_REST_EXCEPTIONS
    @click.argument('app')
    def app(app):
        """Get the metrics of the application in params."""
        instance, uniq = app.split('/')
        if uniq == 'running':
            instances = _find_running_instance(instance, ctx['ws_api'])
        else:
            instances = _find_uniq_instance(instance, uniq, ctx['ws_api'])

        if not instances:
            cli.bad_exit('No instance found with the application name.')

        _LOGGER.debug('Found instance(s): %s', instances)

        for inst, host in instances.items():
            endpoint = _get_endpoint_for_host(ctx['nodeinf_eps'], host)

            _get_app_metrics(endpoint, inst, uniq, outdir=ctx['outdir'],
                             cell_api=ctx['cell_api'])

    @metrics.command()
    @cli.ON_REST_EXCEPTIONS
    @click.argument('servers', nargs=-1)
    @click.option('--services', type=cli.LIST, help='Subset of core services.')
    def sys(servers, services):
        """Get the metrics of the server(s) in params."""
        for server in servers:
            endpoint = _get_endpoint_for_host(ctx['nodeinf_eps'], server)

            _get_server_metrics(endpoint, server, services, ctx['outdir'])

    del running
    del app
    del sys

    return metrics
