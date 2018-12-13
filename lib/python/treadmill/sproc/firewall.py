"""Treadmill firewall IP IPSet synchronizer

This service keeps the Treadmill IP address sets, SET_PROD_SOURCES and
SET_TM_NODES, in sync.

The SET_PROD_SOURCES is the list of known PROD server which are allowed to
connect to PROD containers. It is refreshed every 12 hours from a TAI data
warehouse dump.

The SET_TM_NODES is the list of know Treadmill node IPs (across cells in the
same environment). It is refresh everytime the `/globals/servers` list is
updated in Zookeeper.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import functools
import logging
import os
import socket
import time

import click

from treadmill import context
from treadmill import firewall as fw
from treadmill import dirwatch
from treadmill import iptables
from treadmill import rulefile
from treadmill import utils
from treadmill import watchdog
from treadmill import yamlwrapper as yaml
from treadmill import zknamespace as z

_LOGGER = logging.getLogger(__name__)

_DEFAULT_RULES_DIR = 'rules'
_DEFAULT_CONTAINER_DIR = 'apps'
_DEFAULT_WATCHDOR_DIR = 'watchdogs'
_FW_WATCHER_HEARTBEAT = 60


def _update_nodes_change(data):
    """Update local Treadmill Nodes IP IPSet when the globals server list gets
    updated."""
    servers = yaml.load(data)

    server_ips = []
    for server in servers:
        try:
            server_ip = socket.gethostbyname(server)
            server_ips.append(server_ip)

        except socket.gaierror:
            _LOGGER.warning('Unable to resolve %r', server)
            continue

    iptables.atomic_set(
        iptables.SET_TM_NODES,
        content=server_ips,
        set_type='hash:ip',
        family='inet'
    )


def _init_rules():
    """Initialization of all chains and sets used by the fw service.
    """
    for chain in (iptables.PREROUTING_DNAT, iptables.POSTROUTING_SNAT,
                  iptables.PREROUTING_PASSTHROUGH,
                  iptables.VRING_DNAT, iptables.VRING_SNAT):
        iptables.create_chain('nat', chain)

    iptables.init_set(iptables.SET_PASSTHROUGHS,
                      family='inet', hashsize=1024, maxelem=65536)


def _configure_rules(target):
    """Configures iptables rules.

    The input to the function is target state - a list of (chain, rule) tuples
    that needs to be present.

    The function will sync existing iptables configuration with the target
    state, by adding/removing extra rules.

    :param ``[tuple(chain, Tuple)]`` target:
        Desired set of rules
    """
    chain_configure_callbacks = {
        iptables.PREROUTING_DNAT:
            functools.partial(
                iptables.configure_dnat_rules,
                chain=iptables.PREROUTING_DNAT
            ),
        iptables.POSTROUTING_SNAT:
            functools.partial(
                iptables.configure_snat_rules,
                chain=iptables.POSTROUTING_SNAT
            ),
        iptables.PREROUTING_PASSTHROUGH:
            functools.partial(
                iptables.configure_passthrough_rules,
                chain=iptables.PREROUTING_PASSTHROUGH
            ),
        iptables.VRING_DNAT:
            functools.partial(
                iptables.configure_dnat_rules,
                chain=iptables.VRING_DNAT
            ),
        iptables.VRING_SNAT:
            functools.partial(
                iptables.configure_snat_rules,
                chain=iptables.VRING_SNAT
            ),
    }
    chain_rules = {}
    for chain, rule in target:
        chain_rules.setdefault(chain, set()).add(rule)

    for chain, rules in chain_rules.items():
        if chain in chain_configure_callbacks:
            chain_configure_callbacks[chain](rules)

        else:
            raise ValueError('Unknown rule chain %r' % chain)


def _watcher(root_dir, rules_dir, containers_dir, watchdogs_dir):
    """Treadmill Firewall rule watcher.
    """
    # pylint: disable=too-many-statements

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
        rule_file = os.path.basename(path)
        _LOGGER.info('adding %r', rule_file)
        # The rule is the filename
        chain_rule = rulemgr.get_rule(rule_file)
        if chain_rule is not None:
            chain, rule = chain_rule
            iptables.add_rule(rule, chain=chain)
            if isinstance(rule, fw.PassThroughRule):
                passthrough[rule.src_ip] = (
                    passthrough.setdefault(rule.src_ip, 0) + 1
                )
                _LOGGER.info('Adding passthrough %r', rule.src_ip)
                iptables.add_ip_set(iptables.SET_PASSTHROUGHS, rule.src_ip)
                iptables.flush_pt_conntrack_table(rule.src_ip)
        else:
            _LOGGER.warning('Ignoring unparseable rule %r', rule_file)

    def on_deleted(path):
        """Invoked when a network rule is deleted."""
        # Edge case, if the directory where the rules are kept gets removed,
        # abort
        if path == rulemgr.path:
            _LOGGER.critical('Network rules directory was removed: %r',
                             path)
            utils.sys_exit(1)

        # The rule is the filename
        rule_file = os.path.basename(path)
        _LOGGER.info('Removing %r', rule_file)
        chain_rule = rulemgr.get_rule(rule_file)
        if chain_rule is not None:
            chain, rule = chain_rule
            iptables.delete_rule(rule, chain=chain)
            if isinstance(rule, fw.PassThroughRule):
                if passthrough[rule.src_ip] == 1:
                    # Remove the IPs from the passthrough set
                    passthrough.pop(rule.src_ip)
                    _LOGGER.info('Removing passthrough %r', rule.src_ip)
                    iptables.rm_ip_set(iptables.SET_PASSTHROUGHS, rule.src_ip)
                    iptables.flush_pt_conntrack_table(rule.src_ip)
                else:
                    passthrough[rule.src_ip] -= 1
            elif isinstance(rule, fw.DNATRule):
                if rule.proto == 'udp':
                    iptables.flush_conntrack_table(
                        src_ip=rule.src_ip,
                        src_port=rule.src_port,
                        dst_ip=rule.dst_ip,
                        dst_port=rule.dst_port,
                    )
            elif isinstance(rule, fw.SNATRule):
                if rule.proto == 'udp':
                    iptables.flush_conntrack_table(
                        src_ip=rule.src_ip,
                        src_port=rule.src_port,
                        dst_ip=rule.dst_ip,
                        dst_port=rule.dst_port,
                    )
        else:
            _LOGGER.warning('Ignoring unparseable file %r', rule_file)

    _LOGGER.info('Monitoring fw rules changes in %r', rulemgr.path)
    watch = dirwatch.DirWatcher(rulemgr.path)
    watch.on_created = on_created
    watch.on_deleted = on_deleted

    # Minimal initialization of the all chains and sets
    _init_rules()

    # now that we are watching, prime the rules
    current_rules = rulemgr.get_rules()

    # Bulk apply rules
    _configure_rules(current_rules)
    for _chain, rule in current_rules:
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
    # pylint: disable=too-many-statements

    @click.group()
    def firewall():
        """Manage Treadmill firewall.
        """

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

        @context.GLOBAL.zk.conn.DataWatch(z.path.globals('servers'))
        @utils.exit_on_unhandled
        def _update_global_servers(data, _stat, event):
            """Handle globals servers data node updates."""
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
