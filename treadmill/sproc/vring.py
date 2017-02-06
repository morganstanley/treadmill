"""Treadmill vring manager."""


import signal
import sys

import logging
import yaml

import click

from .. import context
from .. import discovery
from .. import logcontext as lc
from .. import utils
from .. import vring
from .. import zkutils


_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler."""

    @click.command(name='vring')
    @click.argument('manifest', type=click.File('rb'))
    def vring_cmd(manifest):
        """Run vring manager."""
        context.GLOBAL.zk.conn.add_listener(zkutils.exit_on_disconnect)
        app = yaml.load(manifest.read())

        with lc.LogContext(_LOGGER, app['name'], lc.ContainerAdapter) as log:

            utils.validate(app, [('vring', True, dict)])
            ring = app['vring']
            utils.validate(ring, [('rules', True, list), ('cells', True,
                                                          list)])

            if context.GLOBAL.cell not in ring['cells']:
                log.critical('cell %s not listed in vring.',
                             context.GLOBAL.cell)
                sys.exit(-1)

            ringname = 'TM_OUTPUT_RING_%d' % ring['cells'].index(
                context.GLOBAL.cell)

            rules = ring['rules']
            for rule in rules:
                utils.validate(rule, [('pattern', True, str),
                                      ('endpoints', True, list)])

            # Create translation for endpoint name to expected port #.
            routing = {}
            for endpoint in app.get('endpoints', []):
                routing[endpoint['name']] = endpoint['port']

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

            # TODO: discovery is limited to one rule for now.
            if len(rules) != 1:
                log.critical('(TODO): multiple rules are not supported.')
                sys.exit(-1)
            pattern = rules[0]['pattern']

            app_discovery = discovery.Discovery(context.GLOBAL.zk.conn,
                                                pattern, '*')
            app_discovery.sync()

            # Restore default signal mask disabled by python spawning new
            # thread for Zk connection.
            #
            # TODO: should this be done as part of ZK connect?
            for sig in range(1, signal.NSIG):
                try:
                    signal.signal(sig, signal.SIG_DFL)
                except RuntimeError:
                    pass

            vring.init(ringname)
            vring.run(ringname, routing, vring_endpoints, app_discovery)

    return vring_cmd
