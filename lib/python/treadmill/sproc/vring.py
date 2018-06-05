"""Treadmill vring manager.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import json
import logging
import sys

import click

from treadmill import appenv
from treadmill import appcfg
from treadmill import context
from treadmill import discovery
from treadmill import logcontext as lc
from treadmill import utils
from treadmill import vring
from treadmill import zkutils


_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler."""

    @click.command(name='vring')
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.argument('manifest', type=click.Path(exists=True, readable=True))
    def vring_cmd(approot, manifest):
        """Run vring manager."""
        context.GLOBAL.zk.conn.add_listener(zkutils.exit_on_disconnect)
        tm_env = appenv.AppEnvironment(approot)
        with io.open(manifest, 'r') as fd:
            app = json.load(fd)

        with lc.LogContext(_LOGGER, app['name'], lc.ContainerAdapter) as log:

            # TODO(boysson): Remove all validation from here.
            utils.validate(app, [('vring', True, dict)])
            ring = app['vring']
            utils.validate(ring, [('rules', True, list), ('cells', True,
                                                          list)])

            if context.GLOBAL.cell not in ring['cells']:
                log.critical('cell %s not listed in vring.',
                             context.GLOBAL.cell)
                sys.exit(-1)

            rules = ring['rules']
            for rule in rules:
                utils.validate(rule, [('pattern', True, str),
                                      ('endpoints', True, list)])

            # Create translation for endpoint name to expected port #.
            routing = {}
            for endpoint in app.get('endpoints', []):
                routing[endpoint['name']] = {
                    'port': endpoint['port'],
                    'proto': endpoint['proto']
                }

            # Check that all ring endpoints are listed in the manifest.
            vring_endpoints = set()
            for rule in rules:
                for rule_endpoint in rule['endpoints']:
                    if rule_endpoint not in routing:
                        log.critical(
                            'vring references non-existing endpoint: [%s]',
                            rule_endpoint)
                        sys.exit(-1)
                    vring_endpoints.add(rule_endpoint)

            patterns = [rule['pattern'] for rule in rules]
            app_discovery = discovery.Discovery(context.GLOBAL.zk.conn,
                                                patterns, '*')
            app_discovery.sync()

            # Restore default signal mask disabled by python spawning new
            # thread for Zk connection.
            #
            # TODO: should this be done as part of ZK connect?
            utils.restore_signals()

            app_unique_name = appcfg.manifest_unique_name(app)

            vring.run(
                routing,
                vring_endpoints,
                app_discovery,
                tm_env.rules,
                app['network']['vip'],
                app_unique_name,
            )

    return vring_cmd
