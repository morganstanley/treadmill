"""Wrapper for iptables/ipset.
"""
# Disable "too many lines in module" warning.
#
# pylint: disable=C0302

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import random
import re
import shlex
import time

try:
    import xml.etree.cElementTree as etree
except ImportError:
    import xml.etree.ElementTree as etree

from treadmill import firewall
from treadmill import subproc

from treadmill import templates
from treadmill.templates.ipset_host_restore import T as IPSET_HOST_RESTORE
from treadmill.templates.iptables_empty_restore import T \
    as IPTABLES_EMPTY_RESTORE
from treadmill.templates.iptables_filter_table_restore import T \
    as IPTABLES_FILTER_TABLE_RESTORE
from treadmill.templates.iptables_host_restore import T \
    as IPTABLES_HOST_RESTORE


_LOGGER = logging.getLogger(__name__)

#: Chain where to add outgoing traffic DNAT rule (used inside container)
OUTPUT = 'OUTPUT'

#: Chain where to add outgoing traffic SNAT rule (used inside container)
POSTROUTING = 'POSTROUTING'

#: Chain where to add incoming NAT Passthrough rule
PREROUTING_PASSTHROUGH = 'TM_PASSTHROUGH'

#: Chain where to add incoming NAT DNAT redirect rule
PREROUTING_DNAT = 'TM_PREROUTING_DNAT'

#: Chain where to add container outgoing traffic SNAT rule
POSTROUTING_SNAT = 'TM_POSTROUTING_SNAT'

#: Chain where to add container vring DNAT rule
VRING_DNAT = 'TM_PREROUTING_VRING'

#: Chain where to add container vring SNAT rule
VRING_SNAT = 'TM_POSTROUTING_VRING'

#: Chain where to add exception filter rules
EXCEPTION_FILTER = 'TM_EXCEPTION_FILTER'

#: IPSet set of the IPs of all containers using vring
SET_VRING_CONTAINERS = 'tm:vring-containers'
#: IPSet set of the IPs of all NONPROD containers
SET_NONPROD_CONTAINERS = 'tm:nonprod-containers'
#: IPSet set of the IPs of all PROD containers
SET_PROD_CONTAINERS = 'tm:prod-containers'
#: IPSet set of IPs of all containers (union of PROD and NONPROD sets)
_SET_CONTAINERS = 'tm:containers'
#: IPSet set of the IPs know PROD servers/service addresses
SET_PROD_SOURCES = 'tm:prod-sources'
#: IPSet set of the IPs of all Treadmill nodes
SET_TM_NODES = 'tm:nodes'
#: IPSet set of the IP/Port of all services that should bypass environment.
#: filtering.
SET_INFRA_SVC = 'tm:infra-services'
#: IPSet set of the IPs of all containers' passthrough addresses.
SET_PASSTHROUGHS = 'tm:passthroughs'

#: Port span that will be allocated to outgoing PROD and NONPROD connections
PORT_SPAN = 8192
#: Low boundary of the PROD port span
PROD_PORT_LOW = 32768
#: High boundary of the PROD port span
PROD_PORT_HIGH = PROD_PORT_LOW + PORT_SPAN - 1
#: Low boundary of the NONPROD port span
NONPROD_PORT_LOW = PROD_PORT_LOW + PORT_SPAN
#: High boundary of the NONPROD port span
NONPROD_PORT_HIGH = NONPROD_PORT_LOW + PORT_SPAN - 1

#: Mark to use on PROD traffic
_CONNTRACK_PROD_MARK = '0x1/0xffffffff'
#: Mark to use on NONPROD traffic
_CONNTRACK_NONPROD_MARK = '0x2/0xffffffff'


#: Regular expression scrapping DNAT rules
_DNAT_RULE_RE = re.compile(
    r'^'
    # Ignore the chain name
    r'-A \w+ '
    # Original source IP
    r'(?:-s (?P<src_ip>(?:\d{1,3}\.){3}\d{1,3})/32 )?'
    # Original destination IP
    r'(?:-d (?P<dst_ip>(?:\d{1,3}\.){3}\d{1,3})/32 )?'
    # Protocol
    r'-p (?P<proto>(?:tcp|udp)) -m (?P=proto) '
    # Original source Port
    r'(?:--sport (?P<src_port>\d{1,5}) )?'
    # Original destination Port
    r'(?:--dport (?P<dst_port>\d{1,5}) )?'
    # Ignore counters if present
    r'(?:-c \d+ \d+ )?'
    # New IP
    r'-j DNAT --to-destination (?P<new_ip>(?:\d{1,3}\.){3}\d{1,3})'
    # New Port
    r'(?:[:](?P<new_port>\d{1,5}))?'
    r'$'
)

#: String pattern forming SNAT rules for use with iptables
_SNAT_RULE_PATTERN = ('-s {src_ip} -d {dst_ip} -p {proto} -m {_proto}'
                      ' --sport {src_port} --dport {dst_port}'
                      ' -j SNAT --to-source {new_ip}:{new_port}')

#: Regular expression scrapping SNAT rules
_SNAT_RULE_RE = re.compile(
    r'^'
    # Ignore the chain name
    r'-A \w+ '
    # Original source IP
    r'(?:-s (?P<src_ip>(?:\d{1,3}\.){3}\d{1,3})/32 )?'
    # Original destination IP
    r'(?:-d (?P<dst_ip>(?:\d{1,3}\.){3}\d{1,3})/32 )?'
    # Protocol
    r'-p (?P<proto>(?:tcp|udp)) -m (?P=proto) '
    # Original source Port
    r'(?:--sport (?P<src_port>\d{1,5}) )?'
    # Original destination Port
    r'(?:--dport (?P<dst_port>\d{1,5}) )?'
    # Ignore counters if present
    r'(?:-c \d+ \d+ )?'
    # New IP
    r'-j SNAT --to-source (?P<new_ip>(?:\d{1,3}\.){3}\d{1,3})'
    # New Port
    r'(?:[:](?P<new_port>\d{1,5}))?'
    r'$'
)


# TODO(boysson): Fold PassThroughRule into a kind of DNAT rule
#: String pattern forming passthough rules for use with iptables
_PASSTHROUGH_RULE_PATTERN = \
    '-s {src_ip} -j DNAT --to-destination {dst_ip}'

#: Regular expression scrapping PassThrough rules
_PASSTHROUGH_RULE_RE = re.compile((
    # Ignore the chain name
    r'^-A \w+ ' +
    _PASSTHROUGH_RULE_PATTERN.format(
        src_ip=r'(?P<src_ip>(?:\d{1,3}\.){3}\d{1,3})/32',
        dst_ip=r'(?P<dst_ip>(?:\d{1,3}\.){3}\d{1,3})',
    ) +
    r'$'
))

#: Exit code in iptables>=1.4.20 when the table lock is already held.
_IPTABLES_EXIT_LOCKED = 4


def initialize(external_ip):
    """Initialize iptables firewall by bulk loading all the Treadmill static
    rules and enable ip forwarding

    It is assumed that none but Treadmill manages these tables.

    :param ``str`` external_ip:
        External IP to use with NAT rules
    """
    # Ensure all the IPSets exists.
    ipsets_ensure_exist()

    # Do one time IPSet clean up.
    flush_set(_SET_CONTAINERS)
    add_ip_set(_SET_CONTAINERS, SET_PROD_CONTAINERS)
    add_ip_set(_SET_CONTAINERS, SET_NONPROD_CONTAINERS)
    flush_set(SET_INFRA_SVC)
    flush_set(SET_VRING_CONTAINERS)

    iptables_state = templates.render(
        IPTABLES_HOST_RESTORE,
        any_container=_SET_CONTAINERS,
        dnat_chain=PREROUTING_DNAT,
        external_ip=external_ip,
        nodes=SET_TM_NODES,
        nonprod_containers=SET_NONPROD_CONTAINERS,
        nonprod_high=NONPROD_PORT_HIGH,
        nonprod_low=NONPROD_PORT_LOW,
        nonprod_mark=_CONNTRACK_NONPROD_MARK,
        passthroughs=SET_PASSTHROUGHS,
        passthrough_chain=PREROUTING_PASSTHROUGH,
        prod_containers=SET_PROD_CONTAINERS,
        prod_high=PROD_PORT_HIGH,
        prod_low=PROD_PORT_LOW,
        prod_mark=_CONNTRACK_PROD_MARK,
        prod_sources=SET_PROD_SOURCES,
        snat_chain=POSTROUTING_SNAT,
        vring_containers=SET_VRING_CONTAINERS,
        vring_dnat_chain=VRING_DNAT,
        vring_snat_chain=VRING_SNAT,
    )
    _iptables_restore(iptables_state)


def ipsets_ensure_exist():
    """Initialize all used IPSets.
    """
    ipset_rules = templates.render(
        IPSET_HOST_RESTORE,
        any_container=_SET_CONTAINERS,
        infra_services=SET_INFRA_SVC,
        passthroughs=SET_PASSTHROUGHS,
        nodes=SET_TM_NODES,
        nonprod_containers=SET_NONPROD_CONTAINERS,
        prod_containers=SET_PROD_CONTAINERS,
        prod_sources=SET_PROD_SOURCES,
        vring_containers=SET_VRING_CONTAINERS,
    )
    ipset_restore(ipset_rules)


def filter_table_set(filter_in_nonprod_chain, filter_out_nonprod_chain):
    """Initialize the filter table chains' rules with the provided rules.

    NOTE: Requires `SET_INFRA_SVC`, `SET_PROD_CONTAINERS`,
    `SET_NONPROD_CONTAINERS` and `_SET_CONTAINERS` to be already defined.  See
    `func:filter_sets_set`.

    :param filter_in_nonprod_chain:
        prod/nonprod -> non-prod FORWARD filter rules.
    :param filter_out_nonprod_chain:
        non-prod -> prod/nonprod FORWARD filter rules.
    """
    filtering_table = templates.render(
        IPTABLES_FILTER_TABLE_RESTORE,
        any_container=_SET_CONTAINERS,
        infra_services=SET_INFRA_SVC,
        nonprod_mark=_CONNTRACK_NONPROD_MARK,
        prod_containers=SET_PROD_CONTAINERS,
        nonprod_containers=SET_NONPROD_CONTAINERS,
        filter_in_nonprod_chain=filter_in_nonprod_chain,
        filter_out_nonprod_chain=filter_out_nonprod_chain,
        filter_exception_chain=EXCEPTION_FILTER,
    )

    # NOTE: The filter_exception_chain needs to be created separately because
    # iptables-restores always flushes the chains.  Doing it like this allows
    # for 'ensure exists' semantics.
    create_chain('filter', EXCEPTION_FILTER)

    return _iptables_restore(filtering_table, noflush=True)


def initialize_container():
    """Initialize iptables firewall by bulk loading all the Treadmill static
    rules. Container version

    It is assumed that none but Treadmill manages these tables.
    """
    _iptables_restore(templates.render(IPTABLES_EMPTY_RESTORE))


def add_raw_rule(table, chain, rule, safe=False):
    """Adds rule to a fiven table/chain.

    :param ``str`` table:
        Name of the table where the chain resides.
    :param ``str`` chain:
        Name of the chain where to insert the rule.
    :param ``str`` rule:
        Raw iptables rule in the same format as "iptables -S"
    :param ``bool`` safe:
        Query iptables prior to adding to prevent duplicates
    """
    rule_parts = shlex.split(rule)

    if safe:
        # Check if the rule already exists, and if it does, do nothing.
        # iptables exit with rc 1 if rule is not found.
        try:
            _iptables(table, '-C', chain, rule_parts)
            return
        except subproc.CalledProcessError as exc:
            if exc.returncode != 1:
                raise

    _iptables(table, '-A', chain, rule_parts)


def delete_raw_rule(table, chain, rule):
    """Deletes rule from a given table/chain.

    :param ``str`` table:
        Name of the table where the chain resides.
    :param ``str`` chain:
        Name of the chain from where to remove the rule.
    :param ``str`` rule:
        Raw iptables rule
    """
    rule_parts = shlex.split(rule)

    try:
        _iptables(table, '-D', chain, rule_parts)
    except subproc.CalledProcessError as exc:
        if exc.returncode in (1, 2):
            # iptables exit with rc 1 (1.4.7) or 2 (1.4.21) if rule is not
            # found, not fatal when deleting.
            # FIXME: detect version of iptables
            pass
        else:
            raise


def create_chain(table, chain):
    """Creates new chain in the given table.

    :param ``str`` table:
        Name of the table where the chain resides.
    :param ``str`` chain:
        Name of the chain to create
    """
    try:
        _iptables(table, '-N', chain)
    except subproc.CalledProcessError:
        pass


def flush_chain(table, chain):
    """Flush a chain in the given table.

    :param ``str`` table:
        Name of the table where the chain resides.
    :param ``str`` chain:
        Name of the chain to create
    """
    try:
        _iptables(table, '-F', chain)
    except subproc.CalledProcessError:
        pass


def delete_chain(table, chain):
    """Delete a chain in the given table.

    :param ``str`` table:
        Name of the table where the chain resides.
    :param ``str`` chain:
        Name of the chain to delete
    """
    try:
        _iptables(table, '-X', chain)
    except subproc.CalledProcessError:
        pass


def _dnat_rule_format(dnat_rule):
    """Format a DNATRule as a iptables rule.

    :param ``DNATRule`` dnat_rule:
        DNAT rule to insert
    :returns:
        ``str`` -- Iptables DNAT rule.
    """
    rule = '-s {src_ip} -d {dst_ip} -p {proto} -m {proto}'.format(
        proto=dnat_rule.proto,
        src_ip=(dnat_rule.src_ip or '0.0.0.0'),
        dst_ip=(dnat_rule.dst_ip or '0.0.0.0'),
    )
    if dnat_rule.src_port:
        rule += ' --sport {src_port}'.format(
            src_port=dnat_rule.src_port
        )
    if dnat_rule.dst_port:
        rule += ' --dport {dst_port}'.format(
            dst_port=dnat_rule.dst_port
        )
    rule += ' -j DNAT --to-destination {new_ip}:{new_port}'.format(
        new_ip=dnat_rule.new_ip,
        new_port=dnat_rule.new_port,
    )
    return rule


def add_dnat_rule(dnat_rule, chain=PREROUTING_DNAT, safe=False):
    """Adds dnat rule to a given chain.

    :param ``DNATRule`` dnat_rule:
        DNAT rule to insert
    :param ``str`` chain:
        Name of the chain where to insert the new rule. If ``None``, the
        default chain ``PREROUTING_DNAT`` will be picked.
    :param ``bool`` safe:
        Query iptables prior to adding to prevent duplicates
    """
    if chain is None:
        chain = PREROUTING_DNAT

    return add_raw_rule(
        'nat', chain,
        _dnat_rule_format(dnat_rule),
        safe
    )


def delete_dnat_rule(dnat_rule, chain=PREROUTING_DNAT):
    """Deletes dnat rule from a given chain.

    :param ``str`` chain:
        Name of the chain from where to remove the rule. If ``None``, the
        default chain ``PREROUTING_DNAT`` will be picked.
    :param ``DNATRule`` dnat_rule:
        DNAT rule to remove
    """
    if chain is None:
        chain = PREROUTING_DNAT

    return delete_raw_rule(
        'nat', chain,
        _dnat_rule_format(dnat_rule),
    )


def _snat_rule_format(dnat_rule):
    """Format a SNATRule as a iptables rule.

    :param ``SNATRule`` dnat_rule:
        SNAT rule to insert
    :returns:
        ``str`` -- Iptables SNAT rule.
    """
    rule = '-s {src_ip} -d {dst_ip} -p {proto} -m {proto}'.format(
        proto=dnat_rule.proto,
        src_ip=(dnat_rule.src_ip or '0.0.0.0'),
        dst_ip=(dnat_rule.dst_ip or '0.0.0.0'),
    )
    if dnat_rule.src_port:
        rule += ' --sport {src_port}'.format(
            src_port=dnat_rule.src_port
        )
    if dnat_rule.dst_port:
        rule += ' --dport {dst_port}'.format(
            dst_port=dnat_rule.dst_port
        )
    rule += ' -j SNAT --to-source {new_ip}:{new_port}'.format(
        new_ip=dnat_rule.new_ip,
        new_port=dnat_rule.new_port,
    )
    return rule


def add_snat_rule(snat_rule, chain=POSTROUTING_SNAT, safe=False):
    """Adds snat rule to a given chain.

    :param ``SNATRule`` snat_rule:
        SNAT rule to insert
    :param ``str`` chain:
        Name of the chain where to insert the new rule.  If ``None``, the
        default chain ``POSTROUTING_SNAT`` will be picked.
    :param ``bool`` safe:
        Query iptables prior to adding to prevent duplicates
    """
    if chain is None:
        chain = POSTROUTING_SNAT
    return add_raw_rule(
        'nat', chain,
        _snat_rule_format(snat_rule),
        safe
    )


def delete_snat_rule(snat_rule, chain=POSTROUTING_SNAT):
    """Deletes snat rule from a given chain.

    :param ``SNATRule`` snat_rule:
        SNAT rule to remove
    :param ``str`` chain:
        Name of the chain where to insert the new rule.  If ``None``, the
        default chain ``POSTROUTING_SNAT`` will be picked.
    """
    if chain is None:
        chain = POSTROUTING_SNAT
    return delete_raw_rule(
        'nat', chain,
        _snat_rule_format(snat_rule),
    )


def _get_current_dnat_rules(chain):
    """Extract all DNAT rules in chain from iptables.

    :param ``str`` chain:
        Iptables chain to process.
    :returns:
        ``set([DNATRule])`` -- Set of rules.
    """
    if chain is None:
        chain = PREROUTING_DNAT
    rules = set()
    for line in _iptables_output('nat', '-S', chain).splitlines():
        dnat_match = _DNAT_RULE_RE.match(line.strip())
        if dnat_match:
            data = dnat_match.groupdict()
            rule = firewall.DNATRule(
                proto=data['proto'],
                dst_ip=data['dst_ip'],
                dst_port=data['dst_port'],
                src_ip=data['src_ip'],
                src_port=data['src_port'],
                new_ip=data['new_ip'],
                new_port=data['new_port']
            )
            rules.add(rule)
            continue

    return rules


def configure_dnat_rules(target, chain=None):
    """Configures iptables DNAT rules.

    The input to the function is target state - a set of DNAT/SNAT rules that
    needs to be present.

    The function will sync existing iptables configuration with the target
    state, by adding/removing extra rules.

    :param ``set([DNATRule])`` target:
        Desired set of rules
    :param ``str`` chain:
        Name of the chain to process.  If ``None``, the default chain
        ``PREROUTING_DNAT`` will be picked.
    """
    current = _get_current_dnat_rules(chain)

    _LOGGER.info('Current %s DNAT: %s', chain, current)
    _LOGGER.info('Target %s DNAT: %s', chain, target)

    # Sync current and desired state.
    for rule in current - target:
        delete_dnat_rule(rule, chain=chain)
    for rule in target - current:
        add_dnat_rule(rule, chain=chain)


def _get_current_snat_rules(chain):
    """Extract all SNAT rules in chain from iptables.

    :param ``str`` chain:
        Iptables chain to process.
    :returns:
        ``set([SNATRule])`` -- Set of rules.
    """
    if chain is None:
        chain = POSTROUTING_SNAT
    rules = set()
    for line in _iptables_output('nat', '-S', chain).splitlines():
        snat_match = _SNAT_RULE_RE.match(line.strip())
        if snat_match:
            data = snat_match.groupdict()
            rule = firewall.SNATRule(
                proto=data['proto'],
                src_ip=data['src_ip'],
                src_port=data['src_port'],
                dst_ip=data['dst_ip'],
                dst_port=data['dst_port'],
                new_ip=data['new_ip'],
                new_port=data['new_port']
            )
            rules.add(rule)
            continue

    return rules


def configure_snat_rules(target, chain=None):
    """Configures iptables SNAT rules.

    The input to the function is target state - a set of DNAT/SNAT rules that
    needs to be present.

    The function will sync existing iptables configuration with the target
    state, by adding/removing extra rules.

    :param ``set([SNATRule])`` target:
        Desired set of rules
    :param ``str`` chain:
        Name of the chain to process.  If ``None``, the default chain
        ``POSTROUTING_SNAT`` will be picked.
    """
    current = _get_current_snat_rules(chain)

    _LOGGER.info('Current %s SNAT: %s', chain, current)
    _LOGGER.info('Target %s SNAT: %s', chain, target)

    # Sync current and desired state.
    for rule in current - target:
        delete_snat_rule(rule, chain=chain)
    for rule in target - current:
        add_snat_rule(rule, chain=chain)


def _get_current_passthrough_rules(chain):
    """Extract all PassThrough rules from iptables.

    :param ``str`` chain:
        Iptables chain to process.
    :returns:
        ``set([PassThroughRule])`` -- Set of rules.
    """
    rules = set()
    if chain is None:
        chain = PREROUTING_PASSTHROUGH
    for line in _iptables_output('nat', '-S', chain).splitlines():
        match = _PASSTHROUGH_RULE_RE.match(line.strip())
        if match:
            data = match.groupdict()
            rule = firewall.PassThroughRule(
                src_ip=data['src_ip'],
                dst_ip=data['dst_ip']
            )
            rules.add(rule)

    return rules


def configure_passthrough_rules(target, chain=None):
    """Configures iptables PassThrough rules.

    The input to the function is target state - a set of PassThrough rules
    that needs to be present.

    The function will sync existing iptables configuration with the target
    state, by adding/removing extra rules.

    :param ``set([PassThroughRule])`` target:
        Desired set of rules
    :param ``str`` chain:
        Name of the chain to process.
    """
    current = _get_current_passthrough_rules(chain)

    _LOGGER.info('Current PassThrough: %r', current)
    _LOGGER.info('Target PassThrough: %r', target)

    # Sync current and desired state.
    for rule in current - target:
        delete_passthrough_rule(rule, chain=chain)
    for rule in target - current:
        add_passthrough_rule(rule, chain=chain)


def add_passthrough_rule(passthrough_rule, chain=PREROUTING_PASSTHROUGH,
                         safe=False):
    """Configures source nat paththorugh rule.

    Creates a set of iptables rules so that all traffic comming from enumerated
    external ips is routed to container_ip.

    From the perspective of apps running on specified external ips, this
    appears as if container is behind a firewall (real host).

    :param ``PassThroughRule`` passthrough_rule:
        PassThrough rule to insert
    :param ``str`` chain:
        Name of the chain where to insert the new rule.
    :param ``bool`` safe:
        Query iptables prior to adding to prevent duplicates
    """
    if chain is None:
        chain = PREROUTING_PASSTHROUGH
    add_raw_rule(
        'nat', chain,
        _PASSTHROUGH_RULE_PATTERN.format(
            src_ip=passthrough_rule.src_ip,
            dst_ip=passthrough_rule.dst_ip,
        ),
        safe=safe
    )


def delete_passthrough_rule(passthrough_rule, chain=PREROUTING_PASSTHROUGH):
    """Deletes passthrough configuration for given hosts.

    :param ``PassThroughRule`` passthrough_rule:
        PassThrough rule to delete
    :param ``str`` chain:
        Name of the chain where to remove the rule from.
    """
    if chain is None:
        chain = PREROUTING_PASSTHROUGH
    delete_raw_rule(
        'nat', chain,
        _PASSTHROUGH_RULE_PATTERN.format(
            src_ip=passthrough_rule.src_ip,
            dst_ip=passthrough_rule.dst_ip,
        )
    )


def flush_conntrack_table(src_ip=None, src_port=None,
                          dst_ip=None, dst_port=None,
                          reply_src_ip=None, reply_src_port=None,
                          reply_dst_ip=None, reply_dst_port=None,
                          src_nat_ip=None, dst_nat_ip=None):
    """Clear any UDP entry in the conntrack table for a given flow(s).

    This should be run after the forwarding rules have been removed but
    *before* the VIP is reused.

    :param ``str`` src_ip:
        Original source IP of the flow(s) to scrub from the conntrack table.
    :param ``str`` src_port:
        Original source port of the flow(s) to scrub from the conntrack table.
    :param ``str`` dst_ip:
        Original destination IP of the flow(s) to scrub from the conntrack
        table.
    :param ``str`` dst_port:
        Original destination port of the flow(s) to scrub from the conntrack
        table.
    :param ``str`` reply_src_ip:
        Reply source IP of the flow(s) to scrub from the conntrack table.
    :param ``str`` reply_src_port:
        Reply source port of the flow(s) to scrub from the conntrack table.
    :param ``str`` reply_dst_ip:
        Reply destination IP of the flow(s) to scrub from the conntrack table.
    :param ``str`` reply_dst_port:
        Reply destination port of the flow(s) to scrub from the conntrack
        table.
    :param ``str`` src_nat_ip:
        NAT'ed source IP of the flow(s) to scrub from the conntrack table.
    :param ``str`` dst_nat_ip:
        NAT'ed destination IP of the flow(s) to scrub from the conntrack table.
        table.
    """
    # This addresses the case for UDP session in particular.
    #
    # Since netfilter keeps connection state cache for 180 sec by default, udp
    # packets will not be routed if the same rule is recreated, rather they
    # will be routed to previously associated container.
    #
    # Deleting connection state will ensure that netfilter connection tracking
    # works correctly.

    # pylint: disable=too-many-branches
    flow_selectors = []
    if src_ip is not None and src_ip != firewall.ANY_IP:
        flow_selectors.extend(['--orig-src', src_ip])
    if src_port is not None and src_port != firewall.ANY_PORT:
        flow_selectors.extend(['--orig-port-src', str(src_port)])
    if dst_ip is not None and dst_ip != firewall.ANY_IP:
        flow_selectors.extend(['--orig-dst', dst_ip])
    if dst_port is not None and dst_port != firewall.ANY_PORT:
        flow_selectors.extend(['--orig-port-dst', str(dst_port)])

    if reply_src_ip is not None and reply_src_ip != firewall.ANY_IP:
        flow_selectors.extend(['--reply-src', reply_src_ip])
    if reply_src_port is not None and reply_src_port != firewall.ANY_PORT:
        flow_selectors.extend(['--reply-port-src', str(reply_src_port)])
    if reply_dst_ip is not None and reply_dst_ip != firewall.ANY_IP:
        flow_selectors.extend(['--reply-dst', reply_dst_ip])
    if reply_dst_port is not None and reply_dst_port != firewall.ANY_PORT:
        flow_selectors.extend(['--reply-port-dst', str(reply_dst_port)])

    if src_nat_ip is not None and src_nat_ip != firewall.ANY_IP:
        flow_selectors.extend(['--src-nat', src_nat_ip])
    if dst_nat_ip is not None and dst_nat_ip != firewall.ANY_IP:
        flow_selectors.extend(['--dst-nat', dst_nat_ip])

    assert flow_selectors, 'Provide at least one flow selector element'

    try:
        subproc.check_call(
            [
                'conntrack', '-D',
                '--protonum', 'udp'
            ] + flow_selectors
        )
    except subproc.CalledProcessError as exc:
        # return code is 0 if entries were deleted, 1 if no matching
        # entries were found.
        if exc.returncode in (0, 1):
            pass
        else:
            raise


def flush_cnt_conntrack_table(vip):
    """Clear any entry in the conntrack table for a given VIP.

    This should be run after all the forwarding rules have been removed but
    *before* the VIP is reused.

    :param ``str`` vip:
        NAT IP to scrub from the conntrack table.
    """
    flush_conntrack_table(src_nat_ip=vip)
    flush_conntrack_table(dst_nat_ip=vip)


def flush_pt_conntrack_table(passthrough_ip):
    """Clear any entry in the conntrack table for a given passthrough IP.

    This should be run after all the forwarding rules have been removed.

    :param ``str`` passthrough_ip:
        External IP to scrub from the conntrack table.
    """
    flush_conntrack_table(dst_ip=passthrough_ip)
    flush_conntrack_table(src_ip=passthrough_ip)


def add_rule(rule, chain=None):
    """Adds a rule to a given chain.

    :param ``DNATRule|PassThroughRule`` rule:
        Rule to add
    :param ``str`` chain:
        Name of the chain where to insert the new rule. If set to None
        (default), the default chain will be picked based on the rule type.
    """
    if isinstance(rule, firewall.DNATRule):
        add_dnat_rule(rule, chain=chain)

    elif isinstance(rule, firewall.SNATRule):
        add_snat_rule(rule, chain=chain)

    elif isinstance(rule, firewall.PassThroughRule):
        add_passthrough_rule(rule, chain=chain)
    else:
        raise ValueError('Unknown rule type %r' % (type(rule)))


def delete_rule(rule, chain=None):
    """Delete a rule from a given chain.

    :param ``DNATRule|PassThroughRule`` rule:
        Rule to remove
    :param ``str`` chain:
        Name of the chain from which to remove the new rule. If set to None
        (default), the default chain will be picked based on the rule type.
    """
    if isinstance(rule, firewall.DNATRule):
        delete_dnat_rule(rule, chain=chain)

    elif isinstance(rule, firewall.SNATRule):
        delete_snat_rule(rule, chain=chain)

    elif isinstance(rule, firewall.PassThroughRule):
        delete_passthrough_rule(rule, chain=chain)

    else:
        raise ValueError('Unknown rule type %r' % (type(rule)))


def create_set(new_set, set_type='hash:ip', **set_options):
    """Create a new IPSet set"""
    _ipset(
        '-exist', 'create', new_set, set_type,
        # Below expands to a list of k, v, one after the other
        *[str(i) for item in set_options.items() for i in item]
    )


def init_set(new_set, set_type='hash:ip', **set_options):
    """Create/Initialize a new IPSet set

    :param ``str`` new_set:
        Name of the IPSet set
    :param ``str`` set_type:
        Type of the IPSet set
    :param set_options:
        Extra options for the set creation
    """
    create_set(new_set, set_type=set_type, **set_options)
    flush_set(new_set)


def destroy_set(target_set):
    """Destroy an IPSet set.

    :param ``str`` target_set:
        Name of the IPSet set to destroy.
    """
    _ipset('destroy', target_set, use_except=False)


def flush_set(target_set):
    """Flush an IPSet set.

    :param ``str`` target_set:
        Name of the IPSet set to flush.
    """
    _ipset('flush', target_set)


def atomic_set(target_set, content, set_type='hash:ip', **set_options):
    """Atomically set an IPSet to a provided content.

    :param ``str`` target_set:
        Name of the IPSet set
    :param ``iterator`` content:
        Iterator containing the content to load in the set.
    :param ``str`` set_type:
        Type of the IPSet set
    :param set_options:
        Extra options for the set creation
    """
    # TODO: Read the target_set options directly instead of requiring user to
    # provide them to this function.

    # Temporary set is microsecond timestamped
    new_set = 'tmp-{ts}'.format(
        ts=int(time.time() * 10**7)
    )
    assert len(new_set) <= 32, 'Temporary set name too long'
    _LOGGER.debug('Temporary IPSet: %r', new_set)
    try:
        # Create a new empty IPSet set
        create_set(
            new_set,
            set_type=set_type,
            **set_options
        )
        # Add all the data at once using a restore script
        ipset_dump = [
            'add {tmp_set} {data}'.format(
                tmp_set=new_set,
                data=data)
            for data in content
        ]
        ipset_restore('\n'.join(ipset_dump))
        # All synchronized, now replace the old IPSet with the new one
        swap_set(target_set, new_set)
        _LOGGER.info('IPSet %r updated.', target_set)

    finally:
        # Destroy the temporary IPSet set
        destroy_set(new_set)


def list_set(target_set):
    """List members of the set.

    :param ``str`` target_set:
        Name of the IPSet set to list.
    :returns:
        ``list`` -- List of the set member IPs as strings.
    """
    (_res, output) = _ipset(
        'list',
        '-o', 'xml',
        target_set
    )
    # Extract the members from the xml output
    et = etree.fromstring(output)
    return [
        c.text
        for c in et.find('members')
    ]


def list_all_sets():
    """List all sets.

    :returns:
        ``set`` -- Set of names.
    """
    (_res, output) = _ipset(
        'list',
        '-name'
    )
    return set(output.split())


def test_ip_set(target_set, test_ip):
    """Check persence of an IP in an IPSet set

    :param ``str`` target_set:
        Name of the IPSet set to check.
    :param ``str`` test_ip:
        IP address or host to check.
    :returns:
        ``bool`` -- ``True`` if the IP is in the set, ``False`` otherwise.
    """
    (res, _output) = _ipset(
        'test', target_set, test_ip,
        use_except=False
    )
    return bool(res == 0)


def add_ip_set(target_set, add_ip):
    """Add an IP to an IPSet set

    :param ``str`` target_set:
        Name of the IPSet set where to add the IP.
    :param ``str`` add_ip:
        IP address or host to add to the set
    """
    _ipset('-exist', 'add', target_set, add_ip)


def rm_ip_set(target_set, del_ip):
    """Remove an IP from an IPSet set

    :param ``str`` target_set:
        Name of the IPSet set where to add the IP.
    :param ``str`` del_ip:
        IP address or host to remove from the set
    """
    _ipset('-exist', 'del', target_set, del_ip)


def swap_set(from_set, to_set):
    """Swap to IPSet sets

    :param ``str`` from_set:
        Name of the source IPSet set
    :param ``str`` to_set:
        Name of the destination IPSet set.
    """
    _ipset('swap', from_set, to_set)


def ipset_restore(ipset_state):
    """Initializes the IPSet state.

    :param ``str`` ipset_state:
        Target state for IPSet (using `ipset save` syntax)
    """
    _ipset('-exist', 'restore', cmd_input=ipset_state)


def _ipset(*args, **kwargs):
    """Invoke the IPSet command.
    """
    # Default to using exceptions.
    kwargs.setdefault('use_except', True)
    full_cmd = ['ipset'] + list(args)
    return subproc.invoke(full_cmd, **kwargs)


def _iptables(table, action, chain, rules=None):
    """Invoke iptables with the given table, action, chain and rules.
    """
    cmd = ['iptables', '-t', table, action, chain]
    if rules is not None:
        cmd += rules

    _LOGGER.debug('%r', cmd)
    while True:
        try:
            res = subproc.check_call(cmd)
            break
        except subproc.CalledProcessError as err:
            if err.returncode == _IPTABLES_EXIT_LOCKED:
                _LOGGER.debug('xtable locked, retrying.')
                # table locked, spin and try again
                time.sleep(random.uniform(0, 1))
            else:
                raise

    return res


def _iptables_output(table, action, chain):
    """Invoke iptables with the given table, action and chain and capture its
    output.
    """
    cmd = ['iptables', '-t', table, action, chain]

    _LOGGER.debug('%r', cmd)
    while True:
        try:
            res = subproc.check_output(cmd)
            break
        except subproc.CalledProcessError as err:
            if err.returncode == _IPTABLES_EXIT_LOCKED:
                _LOGGER.debug('xtable locked, retrying.')
                # table locked, spin and try again
                time.sleep(random.uniform(0, 1))
            else:
                raise

    return res


def _iptables_restore(iptables_state, noflush=False):
    """Call iptable-restore with the provide tables dump

    :param ``str`` iptables_state:
        Table initialization to pass to iptables-restore
    :param ``bool`` noflush:
        *optional* Do not flush the table before loading the rules.
    """
    # Use logical name (iptables_restore) of the real command.
    cmd = ['iptables_restore']
    if noflush:
        cmd.append('--noflush')

    while True:
        try:
            res = subproc.invoke(cmd,
                                 cmd_input=iptables_state,
                                 use_except=True)
            break
        except subproc.CalledProcessError as err:
            if err.returncode == _IPTABLES_EXIT_LOCKED:
                _LOGGER.debug('xtable locked, retrying.')
                # table locked, spin and try again
                time.sleep(random.uniform(0, 1))
            else:
                raise

    return res
