"""Watch for prodperim file and copy to supplied destination directory.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import itertools
import logging
import os
import random
import sys
import time
import zlib

import click
import kazoo

from treadmill import admin
from treadmill import appenv
from treadmill import context
from treadmill import fs
from treadmill import iptables
from treadmill import services
from treadmill import subproc
from treadmill import utils
from treadmill import zkutils

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import mszknamespace as z
from treadmill.ms import prodperim
from treadmill.ms import taidw


PRODPERIM_RULE_REFRESH = 60 * 60 * 12  # 12 hours
PRODPERIM_RULE_SIZE_LIMIT = utils.size_to_bytes('1M')
BACK_OFF_RANGE = 10  # 10 seconds


_LOGGER = logging.getLogger(__name__)


def _back_off():
    """Back off for random time to avoid clustered requests"""
    back_off_time = random.uniform(0, 1) * BACK_OFF_RANGE
    _LOGGER.info('Back off for %r seconds', back_off_time)
    time.sleep(back_off_time)


def _watch_prodperim(zkclient, path, cache_dir):
    """Watch prodperim rule updates"""
    @zkclient.ChildrenWatch(path)
    @utils.exit_on_unhandled
    def _watch_prodperim_zk(_children):
        _LOGGER.info('Received Prodeperim rule update')
        _sync_rules(zkclient, path, cache_dir)
        return True


def _apply_rules(rules, cache_dir):
    """Apply compressed rules"""
    if prodperim.INBOUND in rules:
        inbound_rules = prodperim.decompress_rules(rules[prodperim.INBOUND])
    else:
        inbound_rules = None
    if prodperim.OUTBOUND in rules:
        outbound_rules = prodperim.decompress_rules(rules[prodperim.OUTBOUND])
    else:
        outbound_rules = None

    _LOGGER.info('Applying prodperim rules')
    iptables.filter_table_set(inbound_rules, outbound_rules)

    _LOGGER.info('Updating local rule cache')
    for direction in rules:
        with io.open(
            os.path.join(cache_dir, prodperim.RULE_CACHE[direction]), 'wb'
        ) as fd:
            fd.write(rules[direction])


def _sync_rules(zkclient, prodperim_path, cache_dir):
    """Sync prodperim rules in zk, local cache and iptables"""
    zk_nodes = prodperim.get_rule_nodes(zkclient, prodperim_path)
    zk_sha1 = prodperim.get_zk_node_sha1(zk_nodes)
    local_sha1 = prodperim.get_local_rule_sha1(cache_dir)
    rules = {}
    empty = True
    for direction in [prodperim.INBOUND, prodperim.OUTBOUND]:
        if zk_sha1[direction] is not None \
                and zk_sha1[direction] != local_sha1[direction]:
            # we have new rules
            _back_off()
            _LOGGER.info(
                'Retrieving new rules from %s',
                '{}/{}'.format(prodperim_path, zk_nodes[direction])
            )
            try:
                compressed_rules, _metadata = zkclient.get(
                    '{}/{}'.format(prodperim_path, zk_nodes[direction])
                )
                rules[direction] = compressed_rules
            except kazoo.client.NoNodeError:
                _LOGGER.warning('Rule node deleted during processing')
        if zk_sha1[direction] is not None \
                or local_sha1[direction] is not None:
            empty = False
    if rules:
        _apply_rules(rules, cache_dir)
    else:
        _LOGGER.info('Local rule cache already up to date')
    return empty


def _apply_local_rules():
    """Apply rules in local prodperim installer"""
    local_prodperim_file = os.path.join(
        prodperim.PP_INSTALLER_PATH,
        prodperim.PP_FIREWALL_FILE
    )
    _LOGGER.info(
        'Applying local prodperim rules %s', local_prodperim_file
    )
    # NOTE: `iptable.filter_table_set` takes Unicode rules
    with io.open(
        local_prodperim_file, mode='r', errors='ignore'
    ) as input_rules_file:
        with io.open(
            local_prodperim_file, mode='r', errors='ignore'
        ) as output_rules_file:
            input_rules = prodperim.parse_local_rules(
                input_rules_file, 'PRODPERIM_INPUT'
            )
            output_rules = prodperim.parse_local_rules(
                output_rules_file, 'PRODPERIM_OUTPUT'
            )
            iptables.filter_table_set(
                input_rules, output_rules
            )


def _update_prodip():
    """Update the list of known production IPs from TAI data.
    """
    try:
        prod_server_ips = taidw.server_ip_gen(
            taidw.env_entry_gen(
                taidw.dump_entry_gen(taidw.SERVER_DAT),
                env='prod'
            )
        )
        prod_service_ips = taidw.service_ip_gen(
            taidw.env_entry_gen(
                taidw.dump_entry_gen(taidw.SERVICE_DAT),
                env='prod'
            )
        )
        vip_ips = taidw.vip_ip_gen(taidw.VIPS_TXT['prod'])

        iptables.atomic_set(
            iptables.SET_PROD_SOURCES,
            content=itertools.chain(
                prod_server_ips,
                prod_service_ips,
                vip_ips
            ),
            set_type='hash:ip',
            family='inet', hashsize=4096, maxelem=262144
        )

    except Exception as _err:
        _LOGGER.exception('Error synchronizing TAI data')
        raise


def _upload_rules(zkclient, path, rules):
    """Upload prodperim rules to the given path"""
    rule_nodes = prodperim.get_rule_nodes(zkclient, path, latest=False)
    current_sha1 = prodperim.get_zk_rule_sha1(zkclient, path)
    directions = [prodperim.INBOUND, prodperim.OUTBOUND]
    for direction in directions:
        if direction in rules:
            compressed = zlib.compress('\n'.join(rules[direction]).encode())
            # no need to upload if checksum is same
            new_sha1 = prodperim.get_data_sha1(compressed)
            if new_sha1 == current_sha1[direction]:
                _LOGGER.info('Same checksum, skip %s %s', path, direction)
                continue
            # make sure rule size within limit
            if sys.getsizeof(compressed) < PRODPERIM_RULE_SIZE_LIMIT:
                acl = zkutils.make_default_acl(None)
                zkclient.create(
                    '{}/{}#{}#'.format(path, direction, new_sha1),
                    compressed,
                    acl=acl,
                    sequence=True,
                    makepath=True
                )
                # remove outdated nodes
                for node in rule_nodes[direction]:
                    zkutils.ensure_deleted(
                        zkclient, '{}/{}'.format(path, node)
                    )
            else:
                # Need to send Watchtower alert as well
                _LOGGER.error(
                    'Fail to upload to %s %s, data size exceeds %s',
                    path,
                    direction,
                    PRODPERIM_RULE_SIZE_LIMIT
                )
        else:
            # to avoid rules fall backwards,
            # we need to remove nodes from old ones to new ones
            for node in rule_nodes[direction]:
                zkutils.ensure_deleted(
                    zkclient, '{}/{}'.format(path, node)
                )


def _fallback_rule():
    """Call this if there is no prodperim rule available"""
    _LOGGER.warning('No up-to-date prodperim rules found')
    if prodperim.is_enabled():
        # when deploying to new dev cell
        _apply_local_rules()
    else:
        # when deploying to new prod cell
        # safe to do nothing here, iptables initialize ensures
        # we either use existing rules or DROP all
        _LOGGER.warning(
            'No prodperim fule found in local prodperim installer'
        )


def _watch_prodperim_root(
        zkclient, prodperim_shared_path, rule_cache_dir
):
    """Watch prodperim root node creation"""
    @zkclient.DataWatch(prodperim_shared_path)
    @utils.exit_on_unhandled
    def _watch_prodperim_root_zk(_data, _stat, event):
        if event is not None and event.type == 'CREATED':
            _LOGGER.info('%s created', prodperim_shared_path)
            _watch_prodperim(
                zkclient,
                prodperim_shared_path,
                rule_cache_dir
            )
            return False
        else:
            return True


def init():
    """Main command handler."""

    @click.group(name='prodperim')
    def prodperim_grp():
        """Manage prodperim files."""
        pass

    @prodperim_grp.command()
    def generate():
        """Query rules from Prodperim API and push to zk."""
        admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
        cell = admin_cell.get(context.GLOBAL.cell)
        pp_api = cell.get('data', {}).get('pp-api', prodperim.PP_API)
        pp_exception_api = cell.get('data', {}).get(
            'pp-exception-api', prodperim.PP_EXCEPTION_API
        )

        zkclient = context.GLOBAL.zk.conn
        zkclient.ensure_path(z.PRODPERIM)
        zkclient.ensure_path(z.path.prodperim(prodperim.SHARED_RULE_CATEGORY))
        zkclient.ensure_path(z.path.prodperim(prodperim.PROID_RULE_CATEGORY))

        while True:
            shared_rules = prodperim.parse_rules(
                prodperim.download_rules(pp_api)
            )
            exception_rules = prodperim.parse_rules(
                prodperim.download_rules(pp_exception_api),
                categorize=True
            )
            _LOGGER.info('Uploading prodperim rules to zk')
            _upload_rules(
                zkclient,
                z.path.prodperim(prodperim.SHARED_RULE_CATEGORY),
                shared_rules[prodperim.SHARED_RULE_CATEGORY]
            )
            for proid in exception_rules:
                _upload_rules(
                    zkclient,
                    z.path.prodperim(prodperim.PROID_RULE_CATEGORY, proid),
                    exception_rules[proid]
                )
            _LOGGER.info('Uploaded.')
            _LOGGER.info('Cleaning up outdated prodperim rules in zk')
            outdated = [
                z.path.prodperim(prodperim.PROID_RULE_CATEGORY, child)
                for child in zkclient.get_children(
                    z.path.prodperim(prodperim.PROID_RULE_CATEGORY)
                )
                if child not in exception_rules
            ]
            for zknode in outdated:
                zkutils.ensure_deleted(zkclient, zknode)
            _LOGGER.info('Cleanup Done.')
            _LOGGER.info('Sleep %i secs before updating again',
                         PRODPERIM_RULE_REFRESH)
            time.sleep(PRODPERIM_RULE_REFRESH)

    @prodperim_grp.command()
    @click.option(
        '--pp-dir',
        help='Directory to dump the ProdPerim file',
        default='/var/tmp/treadmill_prodperim'
    )
    def dump(pp_dir):
        """Dumps ProdPerim rules to a given directory."""
        admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
        cell = admin_cell.get(context.GLOBAL.cell)
        pp_api = cell.get('data', {}).get('pp-api', prodperim.PP_API)
        pp_exception_api = cell.get('data', {}).get(
            'pp-exception-api', prodperim.PP_EXCEPTION_API
        )
        fs.mkdir_safe(pp_dir)

        while True:
            prodperim.dump_rules(pp_dir, pp_api, pp_exception_api)
            _LOGGER.info(
                'ProdPerim rules successfully dumped under %s',
                pp_dir
            )
            _LOGGER.info(
                'Sleep %i secs before dumping ProdPerim rules again',
                PRODPERIM_RULE_REFRESH
            )
            time.sleep(PRODPERIM_RULE_REFRESH)

    @prodperim_grp.command()
    @click.option(
        '--inbound-rule-file', required=True,
        type=click.Path(exists=True, readable=True),
        help='ProdPerim INBOUND rule file'
    )
    @click.option(
        '--outbound-rule-file', required=True,
        type=click.Path(exists=True, readable=True),
        help='ProdPerim OUTBOUND rule file'
    )
    def upload(inbound_rule_file, outbound_rule_file):
        """Upload shared prodperim rules in specified files to zk"""
        _LOGGER.info('Parsing prodperim rules')
        with io.open(inbound_rule_file, 'r') as fd:
            inbound_rules = list(
                prodperim.parse_local_rules(fd, 'PRODPERIM_INPUT')
            )
        with io.open(outbound_rule_file, 'r') as fd:
            outbound_rules = list(
                prodperim.parse_local_rules(fd, 'PRODPERIM_OUTPUT')
            )
        zkclient = context.GLOBAL.zk.conn
        _LOGGER.info('Uploading prodperim rules to zk')
        _upload_rules(
            zkclient,
            z.path.prodperim(prodperim.SHARED_RULE_CATEGORY),
            {
                prodperim.INBOUND: inbound_rules,
                prodperim.OUTBOUND: outbound_rules
            }
        )

    @prodperim_grp.command()
    @click.option(
        '--approot', type=click.Path(exists=True),
        envvar='TREADMILL_APPROOT', required=True
    )
    def sync(approot):
        """
        Watch shared prodperim rules on zk, generate and refresh the iptables
        filter table rules to enable Treadmill specific rules.
        """
        tm_env = appenv.AppEnvironment(approot)
        rule_cache_dir = os.path.join(tm_env.spool_dir, 'prodperim')
        fs.mkdir_safe(rule_cache_dir)

        zkclient = context.GLOBAL.zk.conn
        prodperim_shared_path = z.path.prodperim(
            prodperim.SHARED_RULE_CATEGORY
        )

        try:
            empty = _sync_rules(
                zkclient,
                prodperim_shared_path,
                rule_cache_dir
            )
            if empty:
                _fallback_rule()
        except subproc.CalledProcessError:
            _fallback_rule()

        try:
            _LOGGER.info(
                'Watching %s for further rule updates',
                prodperim_shared_path
            )
            _watch_prodperim(
                zkclient,
                prodperim_shared_path,
                rule_cache_dir
            )
        except kazoo.client.NoNodeError:
            _LOGGER.info('%s not created, watching', prodperim_shared_path)
            _watch_prodperim_root(
                zkclient, prodperim_shared_path, rule_cache_dir
            )

        while True:
            _update_prodip()
            _LOGGER.info('Refreshed TAIDW successfully')
            _LOGGER.info(
                'Sleep %i secs before refreshing TAIDW again',
                PRODPERIM_RULE_REFRESH
            )
            time.sleep(PRODPERIM_RULE_REFRESH)

    @prodperim_grp.command()
    @click.option('--root-dir', type=click.Path(exists=True), required=True)
    @click.option('--watchdogs-dir', default='watchdogs')
    def exception_service(root_dir, watchdogs_dir):
        """Exception rule service"""
        svc = services.ResourceService(
            service_dir=os.path.join(root_dir, 'prodperim_exception_svc'),
            impl='treadmill.ms.services.'
                 'prodperim_exception_service.'
                 'ProdperimExceptionResourceService',
        )
        svc.run(
            watchdogs_dir=os.path.join(root_dir, watchdogs_dir)
        )

    del generate
    del dump
    del upload
    del sync
    del exception_service

    return prodperim_grp
