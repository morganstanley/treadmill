"""Convert Treadmill 2.0 apps and allocations to Treadmill 3.x
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import copy
import io
import logging
import os
import tempfile

import click
import six

from treadmill import cli
from treadmill import restclient
from treadmill import yamlwrapper
from treadmill.cli import configure as cli_configure
from treadmill.cli import allocation as cli_allocation


_LOGGER = logging.getLogger(__name__)

_LAF_TM_ENDPOINT = '/api/cloud/treadmill'

_DISCOVERY_REST_API = 'http://treadmill-rest.ms.com:4000'
_ENDPOINT_URL = '/v2/app/endpoint'

_JSON_HEADERS = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
}

_KRUN = '/ms/dist/aurora/bin/krun'

_DEFAULT_RESTART_COUNT = 3


def _laf_hostport(cell):
    """Get the LAF host port for the given cell.
    """
    url = '{}/{}/treadmlp.laf/http'.format(_ENDPOINT_URL, cell)
    endpoints = restclient.get(_DISCOVERY_REST_API, url).json()

    return 'http://{}:{}'.format(
        endpoints[0]['host'],
        endpoints[0]['port'],
    )


def _tm3ify_app(proid, app):
    """TM3ify the app.
    """
    tm3_app = copy.deepcopy(app)

    del tm3_app['_id']

    if 'archive' in tm3_app:
        del tm3_app['archive']
    if 'affinity' in tm3_app:
        del tm3_app['affinity']
    if 'instances' in tm3_app:
        del tm3_app['instances']
    if 'priority' in tm3_app:
        del tm3_app['priority']

    if 'affinity_limit' in tm3_app:
        tm3_app['affinity_limits'] = {'server': tm3_app['affinity_limit']}
        del tm3_app['affinity_limit']

    if app.get('ephemeral_ports') is not None:
        tm3_app['ephemeral_ports'] = {'tcp': app['ephemeral_ports']}

    for srv in tm3_app.get('services', []):
        restart_count = srv['restart_count']
        if restart_count < 0:
            restart_count = _DEFAULT_RESTART_COUNT
        srv['restart'] = {'limit': restart_count}
        del srv['restart_count']

        if not srv['command'].startswith('krun') and (
                not srv['command'].startswith(_KRUN)):
            srv['command'] = '{} -- {}'.format(_KRUN, srv['command'])

    tm3_app['tickets'] = ['{}@is1.morgan'.format(proid)]

    return tm3_app


def _write_yml(obj, filename=None):
    """Dump object to YAML, optionally to a file.
    """
    yamlargs = dict(explicit_start=True, explicit_end=True)

    if filename:
        with io.open(filename, 'w') as fh:
            yamlwrapper.dump(obj, stream=fh, **yamlargs)
        return

    click.echo('{}\n'.format(
        yamlwrapper.dump(obj, **yamlargs)
    ))


def _convert_app(ctx, laf_hostport, app_name, outdir, noop):
    """Convert the supplied TM2 app to TM3.
    """
    _, app = app_name.split('/')
    proid, _name = app.split('.', 1)
    _LOGGER.info('Converting %s', app_name)

    app_url = '{}/app/{}'.format(_LAF_TM_ENDPOINT, app_name)
    app_obj = restclient.get(
        laf_hostport, app_url, headers=_JSON_HEADERS
    ).json()
    _LOGGER.debug('app_obj: %r', app_obj)

    tm3_app = _tm3ify_app(proid, app_obj)
    _LOGGER.debug('tm3_app: %r', tm3_app)

    click.echo(app)
    if noop:
        _write_yml(tm3_app)
        return

    if outdir:
        filename = os.path.join(outdir, '{}.yml'.format(app))
        _write_yml(tm3_app, filename=filename)
        return

    with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
        manifest = tmpfile.name
        _write_yml(tm3_app, filename=manifest)
        configure = cli_configure.init()
        ctx.invoke(configure, manifest=manifest, appname=app)


def _alloc_assignments(alloc):
    """Get a list of TM3 assignments from TM2 allocation.
    """
    assignments = []
    for assign in alloc['assignments']:
        pattern = assign['pattern']
        if not pattern.startswith('proid:'):
            continue
        assignments.append({
            'pattern': pattern[len('proid:'):],
            'priority': assign['priority'],
        })

    return assignments


def _enon_ids(laf_hostport, tenant_name):
    """Get a list of EON IDs based on the proids.
    """
    tenant_id, _ = tenant_name.split('-', 1)
    tenant_url = '{}/tenant/{}'.format(_LAF_TM_ENDPOINT, tenant_id)

    tenant = restclient.get(
        laf_hostport, tenant_url, headers=_JSON_HEADERS
    ).json()

    return list(six.moves.map(str, tenant['systems']))


def _convert_allocation(ctx, allocation, cells, noop):
    """Convert a TM2 allocation to a TM3 allocation.
    """
    cell, alloc_name = allocation.split('/')
    _LOGGER.debug('cell: %s, alloc_name: %s', cell, alloc_name)

    laf_hostport = _laf_hostport(cell)
    _LOGGER.debug('laf_hostport: %s', laf_hostport)

    alloc_url = '{}/allocation/{}'.format(_LAF_TM_ENDPOINT, allocation)
    alloc = restclient.get(
        laf_hostport, alloc_url, headers=_JSON_HEADERS
    ).json()
    _LOGGER.debug('alloc: %r', alloc)

    if not alloc.get('assignments'):
        cli.bad_exit('No assignments in this allocation, cannot continue')

    assignments = _alloc_assignments(alloc)
    eon_ids = _enon_ids(laf_hostport, alloc_name)
    tenants = ':'.join(alloc_name.split('-'))
    _LOGGER.debug('eon_ids: %r, tenants: %r', eon_ids, tenants)

    if not eon_ids:
        cli.bad_exit('No EON IDs, cannot continue')

    mem = alloc['memory']
    cpu = alloc['cpu']
    disk = alloc['disk']
    env = alloc['environment']
    max_util = alloc.get('max_utilization')

    allocation_grp = cli_allocation.init()
    alloc_cmds = allocation_grp.commands

    systems = ','.join(eon_ids)
    if noop:
        click.echo(
            'treadmill allocation configure {} --systems {}'.format(
                tenants, systems))
    else:
        ctx.invoke(
            alloc_cmds['configure'], allocation=tenants, systems=eon_ids
        )

    for cell in cells:
        if noop:
            cmd = (
                'treadmill allocation reserve {} --env {} --cell {} '
                '--memory {} --cpu {} --disk {}'.format(
                    tenants, env, cell, mem, cpu, disk)
            )
            if max_util is not None:
                cmd += ' --max-utilization {}'.format(str(max_util))

            click.echo(cmd)
        else:
            ctx.invoke(
                alloc_cmds['reserve'], allocation=tenants, systems=eon_ids,
                env=env, cell=cell, max_utilization=max_util,
                memory=mem, cpu=cpu, disk=disk
            )
        for assign in assignments:
            if noop:
                click.echo(
                    'treadmill allocation assign --env {} --cell {} '
                    '--pattern {} --priority {}'.format(
                        env, cell, assign['pattern'], assign['priority']))
            else:
                ctx.invoke(
                    alloc_cmds['assign'], env=env, cell=cell,
                    pattern=assign['pattern'], priority=assign['priority']
                )


def init():  # pylint: disable=R0912
    """Convert TM2 apps and allocations to TM3.
    """
    ctxt = {}

    @click.group()
    @click.option('--noop', help='Do not execute commands, simply output them',
                  is_flag=True, default=False)
    def convert(noop):
        """Convert TM2 apps and allocations to TM3.
        """
        ctxt['noop'] = noop

    @convert.command()
    @click.argument('app_pattern', required=True)
    @click.option('--outdir', help='Optional dir to dump YAML files')
    @click.pass_context
    def app(ctx, app_pattern, outdir):
        """Convert a TM2 app to TM3.
        """
        noop = ctxt['noop']

        cell, tm2_app_pattern = app_pattern.split('/')

        laf_hostport = _laf_hostport(cell)
        _LOGGER.debug('laf_hostport %s', laf_hostport)

        body = {
            'cell': cell,
            'match': tm2_app_pattern,
        }
        app_list_url = '{}/app?verb=list'.format(_LAF_TM_ENDPOINT)

        apps = restclient.post(
            laf_hostport, app_list_url, payload=body, headers=_JSON_HEADERS,
        ).json()

        for app_name in apps:
            _convert_app(ctx, laf_hostport, app_name, outdir, noop)
            click.echo()

    @convert.command()
    @click.argument('allocation', required=True)
    @click.option('--cell', help='TM3 cell to setup allocation',
                  type=cli.LIST, required=True)
    @click.pass_context
    def alloc(ctx, allocation, cell):
        """Convert a TM2 allocation to TM3.
        """
        noop = ctxt['noop']

        _convert_allocation(ctx, allocation, cell, noop)

    del app
    del alloc

    return convert
