"""Prodperim exception service.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import logging
import os
import re
import shutil

import kazoo
import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

from treadmill import context
from treadmill import fs
from treadmill import iptables
from treadmill import logcontext as lc
from treadmill.ms import mszknamespace as z
from treadmill.ms import prodperim

from treadmill.services._base_service import BaseResourceServiceImpl

_LOGGER = logging.getLogger(__name__)

PROID_CHAIN_PREFIX = 'tm-e-'
PROID_IPSET_PREFIX = 'tm:e:'

_PROID_IPSET_RE = re.compile(
    r'tm:e:(?P<proid>(?:\w+))'
)

_PRODPERIM_EXCEPTION_PROTOCOLS = [
    'tcp', 'udp'
]
_PRODPERIM_EXCEPTION_RULE_RE = re.compile((
    # protocol: optional
    r'(?:-p (?P<proto>(?:\w{2,32})) )?'
    # dest network: mandatory
    r'-d (?P<dst_net>(?:(?:\d{1,3}\.){3}\d{1,3}(?:\/\d{1,2})?)) '
    # dest port: optional
    r'(?:--dport (?P<dst_port>(?:\d{1,5}(?:\:\d{1,5})?)) )?'
    # action: all prodperim exceptions should be ACCEPT
    r'-j ACCEPT'
    r'$'
))


def _process_rule(rule, proid_ipset):
    """Process one piece of prodperim exception rule"""
    match = _PRODPERIM_EXCEPTION_RULE_RE.match(rule)
    if match:
        rule_spec = match.groupdict()
        if rule_spec['proto'] is not None and \
                rule_spec['dst_port'] is not None:
            iptables.add_ip_set(
                '{}-port-tmp'.format(proid_ipset),
                '{net},{proto}:{port}'.format(
                    net=rule_spec['dst_net'],
                    proto=rule_spec['proto'],
                    port=rule_spec['dst_port'].replace(':', '-'),
                )
            )
        elif rule_spec['proto'] is not None and rule_spec['dst_port'] is None:
            iptables.add_ip_set(
                '{}-{}-tmp'.format(proid_ipset, rule_spec['proto']),
                rule_spec['dst_net']
            )
        elif rule_spec['proto'] is None and rule_spec['dst_port'] is None:
            for protocol in _PRODPERIM_EXCEPTION_PROTOCOLS:
                iptables.add_ip_set(
                    '{}-{}-tmp'.format(proid_ipset, protocol),
                    rule_spec['dst_net']
                )
        else:
            return


def _update_iptables(proid, rules):
    """Update proid exception rules into iptables.

    Idempotent process, interrupted step can be fixed with a second run.
    This ensures service always recovers to consistent status after restart.
    """
    _LOGGER.info('Updating rules into iptables for %s', proid)
    proid_ipset = '{}{}'.format(PROID_IPSET_PREFIX, proid)
    proid_chain = '{}{}'.format(PROID_CHAIN_PREFIX, proid)
    iptables.create_set(
        proid_ipset,
        hashsize=1024, maxelem=65536
    )
    iptables.create_chain('filter', proid_chain)
    iptables.add_raw_rule(
        'filter', iptables.EXCEPTION_FILTER,
        '-m set --match-set {ipset} src -j {chain}'.format(
            ipset=proid_ipset,
            chain=proid_chain
        ),
        safe=True
    )
    for protocol in _PRODPERIM_EXCEPTION_PROTOCOLS:
        # do not flush current ipset
        iptables.create_set(
            '{}-{}'.format(proid_ipset, protocol),
            set_type='hash:net',
            hashsize=1024, maxelem=65536
        )
        # flush tmp ipset
        iptables.init_set(
            '{}-{}-tmp'.format(proid_ipset, protocol),
            set_type='hash:net',
            hashsize=1024, maxelem=65536
        )
        iptables.add_raw_rule(
            'filter', proid_chain,
            '-p {protocol} -m set --match-set {ipset} dst -j ACCEPT'.format(
                protocol=protocol,
                ipset='{}-{}'.format(proid_ipset, protocol)
            ),
            safe=True
        )
    iptables.create_set(
        '{}-port'.format(proid_ipset),
        set_type='hash:ip,port',
        hashsize=1024, maxelem=65536
    )
    iptables.init_set(
        '{}-port-tmp'.format(proid_ipset),
        set_type='hash:ip,port',
        hashsize=1024, maxelem=65536
    )
    iptables.add_raw_rule(
        'filter', proid_chain,
        '-m set --match-set {ipset} dst,dst -j ACCEPT'.format(
            ipset='{}-port'.format(proid_ipset)
        ),
        safe=True
    )

    for rule in rules:
        _process_rule(rule, proid_ipset)

    for protocol in _PRODPERIM_EXCEPTION_PROTOCOLS:
        iptables.swap_set(
            '{}-{}'.format(proid_ipset, protocol),
            '{}-{}-tmp'.format(proid_ipset, protocol)
        )
    iptables.swap_set(
        '{}-port'.format(proid_ipset),
        '{}-port-tmp'.format(proid_ipset)
    )


def _purge_iptables(proid):
    """Purge proid exception rules from iptables.

    Idempotent process, interrupted step can be fixed with a second run.
    This ensures service always recovers to consistent status after restart.
    """
    _LOGGER.info('Purging rules from iptables for %s', proid)
    proid_ipset = '{}{}'.format(PROID_IPSET_PREFIX, proid)
    proid_chain = '{}{}'.format(PROID_CHAIN_PREFIX, proid)
    iptables.flush_chain('filter', proid_chain)
    try:
        iptables.delete_raw_rule(
            'filter', iptables.EXCEPTION_FILTER,
            '-m set --match-set {ipset} src -j {chain}'.format(
                ipset=proid_ipset,
                chain=proid_chain
            )
        )
    except subprocess.CalledProcessError:
        pass
    iptables.delete_chain('filter', proid_chain)
    iptables.destroy_set(proid_ipset, safe=True)
    for protocol in _PRODPERIM_EXCEPTION_PROTOCOLS:
        iptables.destroy_set(
            '{}-{}'.format(proid_ipset, protocol),
            safe=True
        )
        iptables.destroy_set(
            '{}-{}-tmp'.format(proid_ipset, protocol),
            safe=True
        )
    iptables.destroy_set('{}-port'.format(proid_ipset), safe=True)
    iptables.destroy_set('{}-port-tmp'.format(proid_ipset), safe=True)


class ProdperimExceptionResourceService(BaseResourceServiceImpl):
    """Prodperim exception service implementation."""

    __slots__ = (
        '_cache_dir',
        '_zkclient',
    )

    _CACHE_DIR = 'cache'
    _EXCEPTION_ZK_PATH = z.path.prodperim(prodperim.PROID_RULE_CATEGORY)

    def _pull_rules(self, proid):
        """Pull exception rules for proid."""
        _LOGGER.info('Pulling rules for %s', proid)
        proid_dir = os.path.join(self._cache_dir, proid)
        proid_zk_path = '{}/{}'.format(self._EXCEPTION_ZK_PATH, proid)
        cached_sha1 = prodperim.get_local_rule_sha1(proid_dir)
        zk_nodes = prodperim.get_rule_nodes(self._zkclient, proid_zk_path)
        zk_sha1 = prodperim.get_zk_node_sha1(zk_nodes)
        for direction in [prodperim.INBOUND, prodperim.OUTBOUND]:
            if zk_sha1[direction] is not None \
                    and zk_sha1[direction] != cached_sha1[direction]:
                _LOGGER.info(
                    'Retrieving new rules from %s',
                    '{}/{}'.format(proid_zk_path, zk_nodes[direction])
                )
                try:
                    compressed_rules, _metadata = self._zkclient.get(
                        '{}/{}'.format(proid_zk_path, zk_nodes[direction])
                    )
                    rules = prodperim.decompress_rules(compressed_rules)
                    _update_iptables(proid, rules)
                    fs.mkdir_safe(proid_dir)
                    rule_file = os.path.join(
                        proid_dir, prodperim.RULE_CACHE[direction]
                    )
                    with io.open(rule_file, 'wb') as fd:
                        fd.write(compressed_rules)
                    _LOGGER.info('%s updated.', rule_file)
                except kazoo.client.NoNodeError:
                    _LOGGER.warning('Rule node deleted during processing')

    def _remove_rules(self, proid):
        """Remove exception rules for proid."""
        _purge_iptables(proid)
        _LOGGER.info('Removing rules from cache for %s', proid)
        proid_dir = os.path.join(self._cache_dir, proid)
        try:
            shutil.rmtree(proid_dir)
            _LOGGER.info('%s removed.', proid_dir)
        except OSError:
            _LOGGER.info('No rules for %s', proid)

    def __init__(self):
        super(ProdperimExceptionResourceService, self).__init__()
        self._cache_dir = None
        self._zkclient = context.GLOBAL.zk.conn

    def initialize(self, service_dir):
        super(ProdperimExceptionResourceService, self).initialize(service_dir)
        self._cache_dir = os.path.join(service_dir, self._CACHE_DIR)
        fs.mkdir_safe(self._cache_dir)

    def synchronize(self):
        """Make sure that iptables/cache/zk is in sync."""
        _LOGGER.info('Syncing rules')
        cached_proids = set(os.listdir(self._cache_dir))
        applied_proids = set()
        for set_name in iptables.list_all_sets():
            match = _PROID_IPSET_RE.match(set_name)
            if match:
                applied_proids.add(
                    match.groupdict()['proid']
                )
        requested_proids = set(
            [
                rsrc_name.split('.')[0] for rsrc_name in os.listdir(
                    self._service_rsrc_dir
                )
            ]
        )
        _LOGGER.info(
            'Cached proids: %r, Applied proids: %r, Requested proids: %r',
            cached_proids, applied_proids, requested_proids
        )
        for proid in cached_proids.union(applied_proids) - requested_proids:
            self._remove_rules(proid)
        for proid in requested_proids:
            self._pull_rules(proid)

    def report_status(self):
        return {
            'proids': set(os.listdir(self._cache_dir))
        }

    def on_create_request(self, rsrc_id, rsrc_data):
        proid = rsrc_id.split('.')[0]
        with lc.LogContext(
            _LOGGER,
            rsrc_id,
            adapter_cls=lc.ContainerAdapter
        ) as log:
            log.debug('Create: %r %r', rsrc_id, rsrc_data)
            self._pull_rules(proid)

        if proid in set(os.listdir(self._cache_dir)):
            result = {
                'ipset': '{}{}'.format(PROID_IPSET_PREFIX, proid)
            }
        else:
            result = {}

        return result

    def on_delete_request(self, rsrc_id):
        proid = rsrc_id.split('.')[0]
        with lc.LogContext(
            _LOGGER,
            rsrc_id,
            adapter_cls=lc.ContainerAdapter
        ) as log:
            log.debug('Delete: %r', rsrc_id)
            cached_proids = set(os.listdir(self._cache_dir))
            requested_proids = set(
                [
                    rsrc_name.split('.')[0] for rsrc_name in os.listdir(
                        self._service_rsrc_dir
                    )
                ]
            )
            if proid in cached_proids and proid not in requested_proids:
                self._remove_rules(proid)

        return True
