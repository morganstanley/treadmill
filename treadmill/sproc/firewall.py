"""Treadmill firewall IP IPSet synchronizer

This service keeps the Treadmill IP address sets, SET_PROD_SOURCES and
SET_TM_NODES, in sync.

The SET_PROD_SOURCES is the list of known PROD server which are allowed to
connect to PROD containers. It is refreshed every 12 hours from a TAI data
warehouse dump.

The SET_TM_NODES is the list of know Treadmill node IPs (across cells in the
same environment). It is refresh everytime the `/global/servers` list is
updated in Zookeeper.
"""


import logging
import socket
import time
import os

import click
import yaml

# TODO: now that modules are split in two directories, pylint
#                complaines about core module not found.
# pylint: disable=E0611
from .. import context
from .. import exc
from .. import firewall as fw
from .. import idirwatch
from .. import iptables
from .. import rulefile
from .. import utils
from .. import watchdog


# R0915: Need to refactor long function into smaller pieces.
#
# pylint: disable=R0915

_LOGGER = logging.getLogger(__name__)

_DEFAULT_RULES_DIR = 'rules'
_DEFAULT_CONTAINER_DIR = 'apps'
_DEFAULT_WATCHDOR_DIR = 'watchdogs'
_FW_WATCHER_HEARTBEAT = 60


@exc.exit_on_unhandled
def _update_nodes_change(data):
    """Update local Treadmill Nodes IP IPSet when the global server list gets
    updated."""
    servers = yaml.load(data)

    now = int(time.time())
    new_set = '%s-%d' % (iptables.SET_TM_NODES, now)
    _LOGGER.debug('Temporary IPSet: %r', new_set)

    try:
        # Create a new empty IPSet set
        iptables.init_set(new_set)

        # TODO: why not update ipset once using restore, as in
        #                `_update_prodip` function.
        for server in servers:
            try:
                server_ip = socket.gethostbyname(server)
            except socket.gaierror:
                _LOGGER.warning('Unable to resolve %r', server)
                continue

            iptables.add_ip_set(new_set, server_ip)

        # Replace the old IPSet with the new one
        _LOGGER.info('IPSet %r refreshed', iptables.SET_TM_NODES)
        iptables.swap_set(iptables.SET_TM_NODES, new_set)

    except Exception:
        _LOGGER.exception('Error synchronizing Treadmill node data')
        raise

    finally:
        # Destroy the temporary IPSet set
        iptables.destroy_set(new_set)


# FIXME(boysson): This is *NOT* MS specific
def _watcher(root_dir, rules_dir, containers_dir, watchdogs_dir):
    """Treadmill Firewall rule watcher.
    """
    # Too many branches
    # pylint: disable=R0912
    rules_dir = os.path.join(root_dir, rules_dir)
    containers_dir = os.path.join(root_dir, containers_dir)
    watchdogs_dir = os.path.join(root_dir, watchdogs_dir)

    # Setup the watchdog
    watchdogs = watchdog.Watchdog(watchdogs_dir)
    wd = watchdogs.create(
        'svc-{svc_name}'.format(svc_name='firewall_watcher'),
        '{hb:d}s'.format(hb=_FW_WATCHER_HEARTBEAT * 2),
        'Service firewall watcher failed'
    )

    rulemgr = rulefile.RuleMgr(rules_dir, containers_dir)
    passthrough = {}

    def on_created(path):
        """Invoked when a network rule is created."""
        rule = os.path.basename(path)
        _LOGGER.info('adding %s', rule)
        # The rule is the filename
        rule = rulemgr.get_rule(rule)
        if rule:
            iptables.add_rule(rule)
            if isinstance(rule, fw.PassThroughRule):
                passthrough[rule.src_ip] = (
                    passthrough.setdefault(rule.src_ip, 0) + 1
                )
                _LOGGER.info('Adding passthrough %r', rule.src_ip)
                iptables.add_ip_set(iptables.SET_PASSTHROUGHS, rule.src_ip)
        else:
            _LOGGER.warning('Ignoring unparseable rule %r', rule)

    def on_deleted(path):
        """Invoked when a network rule is deleted."""
        # Edge case, if the directory where the rules are kept gets removed,
        # abort
        if path == rulemgr.path:
            _LOGGER.critical('Network rules directory was removed: %r',
                             path)
            utils.sys_exit(1)

        # The rule is the filename
        rule = os.path.basename(path)
        _LOGGER.info('Removing %s', rule)
        rule = rulemgr.get_rule(rule)
        if rule:
            iptables.delete_rule(rule=rule)
            if isinstance(rule, fw.PassThroughRule):
                if passthrough[rule.src_ip] == 1:
                    # Remove the IPs from the passthrough set
                    passthrough.pop(rule.src_ip)
                    _LOGGER.info('Removing passthrough %r', rule.src_ip)
                    iptables.rm_ip_set(iptables.SET_PASSTHROUGHS, rule.src_ip)
                else:
                    passthrough[rule.src_ip] -= 1

        else:
            _LOGGER.warning('Ignoring unparseable file %r', rule)

    _LOGGER.info('Monitoring dnat changes in %r', rulemgr.path)
    watch = idirwatch.DirWatcher(rulemgr.path)
    watch.on_created = on_created
    watch.on_deleted = on_deleted

    # now that we are watching, prime the rules
    current_rules = rulemgr.get_rules()
    # Bulk apply rules
    iptables.configure_rules(current_rules)

    for rule in current_rules:
        if isinstance(rule, fw.PassThroughRule):
            passthrough[rule.src_ip] = (
                passthrough.setdefault(rule.src_ip, 0) + 1
            )
            # Add the IPs to the passthrough set
            _LOGGER.info('Adding passthrough %r', rule.src_ip)
            iptables.add_ip_set(iptables.SET_PASSTHROUGHS, rule.src_ip)

    _LOGGER.info('Current rules: %r', current_rules)
    while True:
        if watch.wait_for_events(timeout=_FW_WATCHER_HEARTBEAT):
            # Process no more than 5 events between heartbeats
            watch.process_events(max_events=5)

        rulemgr.garbage_collect()
        wd.heartbeat()

    _LOGGER.info('service shutdown.')
    wd.remove()


def init():
    """main command handler."""

    @click.group()
    def firewall():
        """Manage Treadmill firewall."""
        pass

    @firewall.command()
    def node_sync():
        """Treadmill firewall IP IPSet synchronizer.

        This service keeps the Treadmill IP address sets, SET_PROD_SOURCES and
        SET_TM_NODES, in sync.

        The SET_PROD_SOURCES is the list of known PROD server which are allowed
        to connect to PROD containers. It is refreshed every 12 hours from a
        TAI data warehouse dump.

        The SET_TM_NODES is the list of know Treadmill node IPs (across cells
        in the same environment). It is refresh everytime the `/global/servers`
        list is updated in Zookeeper.
        """

        @context.GLOBAL.zk.conn.DataWatch('/global/servers')
        def _update_global_servers(data, _stat, event):
            """Handle '/global/servers' data node updates."""
            if (data is None or
                    (event is not None and event.type == 'DELETED')):
                # Node doesn't exists / removed
                return True

            else:
                _update_nodes_change(data)
                return True

        while True:
            time.sleep(60 * 60 * 12)  # 12 hours

    @firewall.command()
    @click.option('--root-dir', required=True,
                  help='Treadmill root dir.')
    @click.option('--rules-dir', help='network rules directory.',
                  default=_DEFAULT_RULES_DIR)
    @click.option('--containers-dir', help='containers directory.',
                  default=_DEFAULT_CONTAINER_DIR)
    @click.option('--watchdogs-dir', help='watchdogs directory.',
                  default=_DEFAULT_WATCHDOR_DIR)
    def watcher(root_dir, rules_dir, containers_dir, watchdogs_dir):
        """Treadmill Firewall rule watcher."""

        return _watcher(root_dir, rules_dir, containers_dir, watchdogs_dir)

    del node_sync
    del watcher
    return firewall
