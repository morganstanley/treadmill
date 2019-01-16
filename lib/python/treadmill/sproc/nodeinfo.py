"""Node info sproc module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import socket

import click
import limits

from treadmill import appenv
from treadmill import cli
from treadmill import context
from treadmill import endpoints
from treadmill import rest
from treadmill import sysinfo
from treadmill import utils
from treadmill import yamlwrapper as yaml
from treadmill import zknamespace as z
from treadmill import zkutils
from treadmill.rest import api
from treadmill.rest import error_handlers  # pylint: disable=W0611

_LOGGER = logging.getLogger(__name__)


def _validate_rate_limit(_ctx, _param, value):
    """Validate rate limit string."""
    if value is None:
        return None
    try:
        limits.parse_many(value)
    except ValueError:
        raise click.BadParameter('Rate limit format: n/second, m/minute, etc.')
    return value


def _get_rate_limit(global_rule, module_rule):
    """Get rate limit rule."""
    limit = {}
    if global_rule is not None:
        limit['_global'] = global_rule

    if module_rule is not None:
        for name, value in module_rule.items():
            _validate_rate_limit(None, None, value)
            limit[name] = value

    return limit if limit else None


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('-r', '--register', required=False, default=False,
                  is_flag=True, help='Register as /nodeinfo in Zookeeper.')
    @click.option('-p', '--port', required=False, default=0)
    @click.option('-a', '--auth', type=click.Choice(['spnego']))
    @click.option('-m', '--modules', help='API modules to load.',
                  required=False, type=cli.LIST)
    @click.option('--config', help='API configuration.', multiple=True,
                  type=(str, click.File()))
    @click.option('-t', '--title', help='API Doc Title',
                  default='Treadmill Nodeinfo REST API')
    @click.option('-c', '--cors-origin', help='CORS origin REGEX')
    @click.option('--rate-limit', 'rate_limit_global',
                  required=False, callback=_validate_rate_limit,
                  help='Global request rate limit rule (eg. "5/second")')
    @click.option('--rate-limit-module',
                  required=False, type=cli.DICT,
                  help='Modular request rate limit rule '
                       '(eg. "cgroup=1/second,local=2/minute")')
    def server(approot, register, port, auth, modules, config, title,
               cors_origin, rate_limit_global, rate_limit_module):
        """Runs nodeinfo server."""
        rate_limit = _get_rate_limit(rate_limit_global, rate_limit_module)

        if port == 0:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('0.0.0.0', 0))
            port = sock.getsockname()[1]
            sock.close()

        hostname = sysinfo.hostname()
        hostport = '%s:%s' % (hostname, port)

        if register:
            zkclient = context.GLOBAL.zk.conn
            zkclient.add_listener(zkutils.exit_on_lost)

            appname = 'root.%s#%010d' % (hostname, os.getpid())
            app_pattern = 'root.%s#*' % (hostname)
            path = z.path.endpoint(appname, 'tcp', 'nodeinfo')
            _LOGGER.info('register endpoint: %s %s', path, hostport)
            zkutils.create(zkclient, path, hostport,
                           acl=[zkclient.make_servers_acl()],
                           ephemeral=True)

            # TODO: remove "legacy" endpoint registration once conversion is
            #       complete.
            tm_env = appenv.AppEnvironment(approot)

            endpoints_mgr = endpoints.EndpointsMgr(tm_env.endpoints_dir)
            endpoints_mgr.unlink_all(
                app_pattern, endpoint='nodeinfo', proto='tcp'
            )

            # On Linux endpoint for nodeinfo is a symlink pointing to
            # /proc/{pid}, on Windows it's just a regular file
            owner = '/proc/{}'.format(os.getpid()) if os.name == 'posix' \
                else None

            endpoints_mgr.create_spec(
                appname=appname,
                endpoint='nodeinfo',
                proto='tcp',
                real_port=port,
                pid=os.getpid(),
                port=port,
                owner=owner,
            )

        _LOGGER.info('Starting nodeinfo server on port: %s', port)

        utils.drop_privileges()

        api_paths = []
        if modules:
            api_modules = {module: None for module in modules}
            for module, cfg in config:
                if module not in api_modules:
                    raise click.UsageError(
                        'Orphan config: %s, not in: %r' % (module, api_modules)
                    )
                api_modules[module] = yaml.load(stream=cfg)
                cfg.close()

            api_paths = api.init(
                api_modules,
                title.replace('_', ' '),
                cors_origin
            )

        rest_server = rest.TcpRestServer(port, auth_type=auth,
                                         protect=api_paths,
                                         rate_limit=rate_limit)
        rest_server.run()

    return server
