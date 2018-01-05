"""Interface with the ProdPerim system.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import hashlib
import io
import logging
import os
import re
import socket
import zlib

import kazoo
from six.moves import urllib_parse

from treadmill import restclient
from treadmill import utils

_LOGGER = logging.getLogger(__name__)

PP_API = 'http://prodperim-transport-prod.gslb.ms.com:9497' \
         '/treadmill/central-rules-json?version=v3'

PP_EXCEPTION_API = 'http://prodperim-transport-prod.gslb.ms.com:9497' \
                   '/treadmill/central-rules-json?version=v3&query_mode=proid'

#: Shared rules go to this category
SHARED_RULE_CATEGORY = 'share'
PROID_RULE_CATEGORY = 'proid'

#: Standard path to ProdPerim install folder
PP_INSTALLER_PATH = '/var/tmp/prodperim/installer/'

# NOTE: Be careful with Aquilon/Aurora DNS discrepancies.
#: Standard name of ProdPerim rule file
PP_FIREWALL_FILE = '{hostname}.fw'.format(hostname=socket.gethostname())

#: Standard name of ProdPerim proid exception rule file
PP_EXCEPTION_FIREWALL_FILE = '{hostname}.exception.fw'.format(
    hostname=socket.gethostname()
)

#: Standard name of the ProdPerim schedule file
PP_SCHEDULE_FILE = PP_FIREWALL_FILE + '.schedule'

#: Standard name of ProdPerim rule generation status file
PP_FIREWALL_STATUS_FILE = 'status'

_PP_RULE_ACTION_MAPPING = {
    'ALLOW': 'ACCEPT',
    'DENY': 'REJECT',
    'DROP': 'DROP',
    'LOG': 'LOG'
}
INBOUND = 'INBOUND'
OUTBOUND = 'OUTBOUND'

RULE_CACHE = {
    INBOUND: 'inbound.rules.cache',
    OUTBOUND: 'outbound.rules.cache'
}

_MAX_IP = 4294967295
_MAX_PORT = 65535


def decompress_rules(compressed_rules):
    """Decompress rules"""
    rule_str = zlib.decompress(compressed_rules)
    if rule_str.strip():
        rules = rule_str.decode().split('\n')
    else:
        rules = []
    return rules


def get_data_sha1(data):
    """Get sha1 of data"""
    hash_object = hashlib.sha1(data)
    return hash_object.hexdigest()


def get_rule_nodes(zkclient, path, latest=True):
    """Get rule nodes of the given prodperim path"""
    result = {}
    try:
        nodes = zkclient.get_children(path)
    except kazoo.client.NoNodeError:
        nodes = []
    for direction in [INBOUND, OUTBOUND]:
        filtered_nodes = sorted(
            [node for node in nodes if node.startswith(direction)],
            key=lambda x: int(x.split('#')[-1])
        )
        if latest:
            if not filtered_nodes:
                result[direction] = None
            else:
                result[direction] = filtered_nodes[-1]
        else:
            result[direction] = filtered_nodes
    return result


def get_zk_node_sha1(rule_nodes):
    """Get sha1 of rule nodes"""
    result = {}
    for direction in rule_nodes:
        if rule_nodes[direction] is None:
            result[direction] = None
        else:
            result[direction] = rule_nodes[direction].split('#')[1]
    return result


def get_zk_rule_sha1(zkclient, path):
    """Get sha1 of rule nodes under given prodperim path"""
    return get_zk_node_sha1(
        get_rule_nodes(zkclient, path)
    )


def get_local_rule_sha1(cache_dir):
    """Get sha1 of local cache rules"""
    result = {}
    for direction in [INBOUND, OUTBOUND]:
        try:
            with io.open(
                os.path.join(cache_dir, RULE_CACHE[direction]), 'rb'
            ) as fd:
                compressed_rules = fd.read()
                result[direction] = get_data_sha1(compressed_rules)
        except (IOError, zlib.error):
            result[direction] = None
    return result


def download_rules(api):
    """Download json rules from prodperim api"""
    _LOGGER.info('Requesting prodperim api %s', api)
    parsed = urllib_parse.urlparse(api)
    resp = restclient.get(
        '{scheme}://{netloc}'.format(
            scheme=parsed.scheme, netloc=parsed.netloc
        ),
        '{path}?{query}'.format(
            path=parsed.path, query=parsed.query
        )
    )
    return resp.json()


def parse_rules(rules, categorize=False):
    """
    Parse json rules from prodperim api

    :param rules: json rules
    :param categorize: whether to categorize by proid
    """
    _LOGGER.info('Parsing prodperim rules')
    rules_mapping = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    if categorize:
        for rule in rules['rules']:
            if rule['prod_id'] != '':
                rules_mapping[rule['prod_id']][rule['direction']].extend(
                    _parse_rule(rule)
                )
        _LOGGER.info('Parsed rules for %r proids', len(rules_mapping))
    else:
        for rule in rules['rules']:
            rules_mapping[SHARED_RULE_CATEGORY][rule['direction']].extend(
                _parse_rule(rule)
            )
        _LOGGER.info(
            'Parsed %r shared inbound rules',
            len(rules_mapping[SHARED_RULE_CATEGORY][INBOUND])
        )
        _LOGGER.info(
            'Parsed %r shared outbound rules',
            len(rules_mapping[SHARED_RULE_CATEGORY][OUTBOUND])
        )
    return rules_mapping


def _parse_rule(rule):
    """Parse one piece of json rule"""
    # Disable too many branches warning.
    #
    # pylint: disable=R0912
    # handle direction (skip the rule if there is unexpected direction)
    direction = rule['direction']
    if direction == OUTBOUND:
        ip_mark = 'd'
    elif direction == INBOUND:
        ip_mark = 's'
    else:
        return []

    # handle protocol
    protocol = rule['protocol'].lower()
    if protocol != 'any':
        protocol_list = ['-p {}'.format(protocol)]
    else:
        protocol_list = ['']

    # handle ip
    ip_int_start = rule['ip_int_start']
    ip_int_end = rule['ip_int_end']
    if ip_int_start != 0 or ip_int_end != _MAX_IP:
        ip_list = []
        for network in utils.cidr_range(ip_int_start, ip_int_end):
            if '/32' in str(network):
                ip_list.append('-{} {}'.format(
                    ip_mark,
                    str(network.network_address)
                ))
            else:
                ip_list.append('-{} {}'.format(ip_mark, str(network)))
    else:
        ip_list = ['']

    # handle port
    port_start = rule['port_start']
    port_end = rule['port_end']
    if port_start != 0 or port_end != _MAX_PORT:
        if port_start == port_end:
            port_list = ['--dport {}'.format(port_start)]
        else:
            port_list = ['--dport {}:{}'.format(port_start, port_end)]
    else:
        port_list = ['']

    # handle action (skip the rule if there is unexpected action)
    action = rule['action'].upper()
    is_log = rule['is_log']
    if action in _PP_RULE_ACTION_MAPPING:
        if is_log == 0:
            action_list = ['-j {}'.format(_PP_RULE_ACTION_MAPPING[action])]
        else:
            action_list = ['-j {}_N_LOG_FORWARD'.format(
                _PP_RULE_ACTION_MAPPING[action]
            )]
    else:
        action_list = []

    # skip illegal rule
    if protocol_list == [''] and port_list != ['']:
        return []

    # put these parts together
    return [
        ' '.join(
            ' '.join([_protocol, _ip, _port, _action]).split()
        ) for _protocol in protocol_list
        for _ip in ip_list
        for _port in port_list
        for _action in action_list
    ]


def dump_rules(rule_dir, pp_api, pp_exception_api):
    """Generate ProdPerim rules for this host.

    this touches a `.schedule` file once the dump is complete.
    """
    _LOGGER.debug('Generating a new ProdPerim rule dump under %r', rule_dir)
    shared_rules = parse_rules(download_rules(pp_api))
    exception_rules = parse_rules(
        download_rules(pp_exception_api),
        categorize=True
    )
    with io.open(os.path.join(rule_dir, 'treadmill.inbound.fw'), 'w') as fd:
        fd.write('\n'.join(shared_rules[SHARED_RULE_CATEGORY][INBOUND]))
    with io.open(os.path.join(rule_dir, 'treadmill.outbound.fw'), 'w') as fd:
        fd.write('\n'.join(shared_rules[SHARED_RULE_CATEGORY][OUTBOUND]))
    with io.open(
        os.path.join(rule_dir, 'treadmill.exception.inbound.fw'), 'w'
    ) as fd:
        for proid in exception_rules:
            fd.write('\n'.join(exception_rules[proid][INBOUND]))
            fd.write('\n')
    with io.open(
        os.path.join(rule_dir, 'treadmill.exception.outbound.fw'), 'w'
    ) as fd:
        for proid in exception_rules:
            fd.write('\n'.join(exception_rules[proid][OUTBOUND]))
            fd.write('\n')
    with io.open(os.path.join(rule_dir, 'treadmill.schedule'), 'w'):
        pass


def parse_local_rules(local_rules, match_chain):
    """
    Parse ProdPerim rules in local Prodperim installer,
    extracting all INPUT/OUTPUT rules into FORWARD rules.
    """
    # RegExp to match every ProdPerim INPUT/OUTPUT rules.
    pp_output_re = re.compile(
        r'^-A {} (?P<rule>.*)'
        r' -j (?:'
        r'(?:'
        r'(?P<logtarget>(?:ACCEPT|LOG|DROP|REJECT)_N_LOG_)(?:INPUT|OUTPUT)'
        r')|'
        r'(?P<target>.*)'
        r')'
        r'$'.format(match_chain)
    )
    for rule in local_rules:
        match = pp_output_re.match(rule)
        if match is not None:
            if match.groupdict().get('logtarget'):
                # We have a LOG target to rewrite
                rule = match.expand(r'\g<rule> -j \g<logtarget>FORWARD')
            else:
                rule = match.expand(r'\g<rule> -j \g<target>')
            yield rule


def is_enabled():
    """Check if ProdPerim is enabled on this host.

    :returns:
        `True` if ProdPerim is enabled, `False` otherwise.
    """
    pp_status_file = os.path.join(
        PP_INSTALLER_PATH,
        PP_FIREWALL_STATUS_FILE
    )
    status = False
    try:
        with io.open(pp_status_file) as status_file:
            if status_file.readlines() == ['success']:
                _LOGGER.info('ProdPerim enabled')
                status = True
            else:
                _LOGGER.info('ProdPerim disabled')

    except IOError:
        _LOGGER.info('ProdPerim disabled (no status file)')

    return status
