"""Wrapper for iptables/ipset"""

import logging
import re
import subprocess

import jinja2

from . import firewall
from . import subproc

_LOGGER = logging.getLogger(__name__)

JINJA2_ENV = jinja2.Environment(loader=jinja2.PackageLoader(__name__))

#: Chain where to add outgoing traffic NAT rule (used inside container)
OUTPUT = 'OUTPUT'

#: Chain where to add incoming NAT Passthrough rule
PREROUTING_PASSTHROUGH = 'TM_PASSTHROUGH'

#: Chain where to add incoming NAT DNAT redirect rule
PREROUTING_DNAT = 'TM_DNAT'

#: IPSet set of the IPs of all NONPROD containers
_SET_NONPROD_CONTAINERS = 'tm:nonprod-containers'
#: IPSet set of the IPs of all PROD containers
_SET_PROD_CONTAINERS = 'tm:prod-containers'
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

#: Iptables tables initial state template.
#: To be used with `iptables-restore`
#:
#: We set up 2 rule sets, TM_MARK_NONPROD and TM_MARK_PROD, in the `mangle`
#: table that will mark all packets as PROD or NONPROD using conntrack marking.
#: Then in the TM_MARK chain, we dispatch traffic coming from containers and
#: external hosts through the appropriate chain.
#:
#: In the `nat` table, we create two rule sets, TM_POSTROUTING_NONPROD and
#: TM_POSTROUTING_PROD, that will put all outgoing connections into a
#: predetermined port range depending on the above mark.
#:
_IPTABLES_TABLES = JINJA2_ENV.get_template('iptables-host-restore')

#: IPSet initial state template
_IPSET_SETS = JINJA2_ENV.get_template('ipset-host-restore')

#: Iptables chain implementing environment filtering.
_IPTABLES_FILTER_TABLE = JINJA2_ENV.get_template(
    'iptables-filter-table-restore'
)

#: Iptables tables, generated with `iptables-save`, used to set the initial
#: state of the Treadmill container rules.
#:
_IPTABLES_EMPTY_TABLES = JINJA2_ENV.get_template('iptables-empty-restore')

#: String pattern forming DNAT rules for use with iptables
_DNAT_RULE_PATTERN = ('-d {orig_ip} -p {proto} -m {_proto} --dport {orig_port}'
                      ' -j DNAT --to-destination {new_ip}:{new_port}')

#: Regular expression scrapping DNAT rules
_DNAT_RULE_RE = re.compile((
    r'^-A \w+ ' +
    # Ignore the chain name
    _DNAT_RULE_PATTERN.format(
        # Original IP
        orig_ip=r'(?P<orig_ip>(?:\d{1,3}\.){3}\d{1,3})/32',
        # Protocol
        proto=r'(?P<proto>(?:tcp|udp))',
        _proto=r'(?P=proto)',
        # Original Port
        orig_port=r'(?P<orig_port>\d{1,5})',
        # New IP
        new_ip=r'(?P<new_ip>(?:\d{1,3}\.){3}\d{1,3})',
        # New Port
        new_port=r'(?P<new_port>\d{1,5})',
    ) +
    r'$'
))

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

#: Container environment to ipset set.
_SET_BY_ENVIRONMENT = {
    'dev': _SET_NONPROD_CONTAINERS,
    'qa': _SET_NONPROD_CONTAINERS,
    'uat': _SET_NONPROD_CONTAINERS,
    'prod': _SET_PROD_CONTAINERS,
}


def initialize(external_ip):
    """Initialize iptables firewall by bulk loading all the Treadmill static
    rules and enable ip forwarding

    It is assumed that none but Treadmill manages these tables.

    :param external_ip:
        External IP to use with NAT rules
    :type external_ip:
        ``str``
    """
    ipset_rules = _IPSET_SETS.render(
        any_container=_SET_CONTAINERS,
        infra_services=SET_INFRA_SVC,
        passthroughs=SET_PASSTHROUGHS,
        nodes=SET_TM_NODES,
        nonprod_containers=_SET_NONPROD_CONTAINERS,
        prod_containers=_SET_PROD_CONTAINERS,
        prod_sources=SET_PROD_SOURCES,
    )
    ipset_restore(ipset_rules)

    iptables_state = _IPTABLES_TABLES.render(
        external_ip=external_ip,
        any_container=_SET_CONTAINERS,
        nodes=SET_TM_NODES,
        nonprod_containers=_SET_NONPROD_CONTAINERS,
        nonprod_high=NONPROD_PORT_HIGH,
        nonprod_low=NONPROD_PORT_LOW,
        nonprod_mark=_CONNTRACK_NONPROD_MARK,
        prod_containers=_SET_PROD_CONTAINERS,
        prod_high=PROD_PORT_HIGH,
        prod_low=PROD_PORT_LOW,
        prod_mark=_CONNTRACK_PROD_MARK,
        prod_sources=SET_PROD_SOURCES,
        dnat_chain=PREROUTING_DNAT,
        passthroughs=SET_PASSTHROUGHS,
        passthrough_chain=PREROUTING_PASSTHROUGH,
    )
    _iptables_restore(iptables_state)

    # Try to load the iptables Filter tables without touching the ProdPerim
    # rules.
    _LOGGER.debug('Reloading Treadmill filter rules')
    try:
        filter_table_set(None)

    except subprocess.CalledProcessError:
        # We were not able to load without a NONPROD rule (filtering not setup
        # yet?).
        # Insert a default rule that drop all non-prod traffic by default until
        # the proper rules are loaded.
        _LOGGER.debug('Reloading Treadmill filter rules (drop all NONPROD)')
        filter_table_set(('-j DROP',))


def filter_table_set(filter_chain):
    """Initialize the environment based filtering rule with the provided rules.
    """
    filtering_table = _IPTABLES_FILTER_TABLE.render(
        any_container=_SET_CONTAINERS,
        infra_services=SET_INFRA_SVC,
        nonprod_mark=_CONNTRACK_NONPROD_MARK,
        prod_containers=_SET_PROD_CONTAINERS,
        filter_chain=filter_chain,
    )
    return _iptables_restore(filtering_table, noflush=True)


def initialize_container():
    """Initialize iptables firewall by bulk loading all the Treadmill static
    rules. Container version

    It is assumed that none but Treadmill manages these tables.
    """
    _iptables_restore(_IPTABLES_EMPTY_TABLES.render())


def add_raw_rule(table, chain, rule, safe=False):
    """Adds rule to a fiven table/chain.

    :param table:
        Name of the table where the chain resides.
    :type table:
        ``str``
    :param chain:
        Name of the chain where to insert the rule.
    :type chain:
        ``str``
    :param rule:
        Raw iptables rule in the same format as "iptables -S"
    :type rule:
        ``str``
    :param safe:
        Query iptables prior to adding to prevent duplicates
    :param safe:
        ``bool``
    """
    add_cmd = ['iptables', '-t', table, '-A', chain] + rule.split()
    _LOGGER.info("%s", add_cmd)
    if safe:
        # Check if the rule already exists, and if it is, do nothing.
        list_cmd = ['iptables', '-t', table, '-S', chain]
        _LOGGER.info("%s", list_cmd)
        lines = [line.strip() for line in
                 subproc.check_output(list_cmd).splitlines()]
        match = '-A %s %s' % (chain, rule)
        if match in lines:
            return

    subproc.check_call(add_cmd)


def delete_raw_rule(table, chain, rule):
    """Deletes rule from a given table/chain.

    :param table:
        Name of the table where the chain resides.
    :type table:
        ``str``
    :param chain:
        Name of the chain from where to remove the rule.
    :type chain:
        ``str``
    :param rule:
        Raw iptables rule
    :type rule:
        ``str``
    """
    del_cmd = ['iptables', '-t', table, '-D', chain] + rule.split()
    _LOGGER.info("%s", del_cmd)

    try:
        subproc.check_call(del_cmd)
    except subprocess.CalledProcessError as exc:
        if exc.returncode == 1:
            # iptables exit with rc 1 if rule is not found, not fatal when
            # deleting.
            pass
        else:
            raise


def create_chain(table, chain):
    """Creates new chain in the given table.

    :param table:
        Name of the table where the chain resides.
    :type table:
        ``str``
    :param chain:
        Name of the chain to create
    :type chain:
        ``str``
    """
    subproc.call(['iptables', '-t', table, '-N', chain])


def add_dnat_rule(dnat_rule, chain=PREROUTING_DNAT, safe=False):
    """Adds dnat rule to a given chain.

    :param dnat_rule:
        DNAT rule to insert
    :type dnat_rule:
        ``DNATRule``
    :param chain:
        Name of the chain where to insert the new rule. If ``None``, the
        default chain ``PREROUTING_DNAT`` will be picked.
    :type chain:
        ``str``
    :param safe:
        Query iptables prior to adding to prevent duplicates
    :param safe:
        ``bool``
    """
    if chain is None:
        chain = PREROUTING_DNAT
    return add_raw_rule(
        'nat', chain,
        _DNAT_RULE_PATTERN.format(
            proto=dnat_rule.proto,
            _proto=dnat_rule.proto,
            orig_ip=dnat_rule.orig_ip,
            orig_port=dnat_rule.orig_port,
            new_ip=dnat_rule.new_ip,
            new_port=dnat_rule.new_port,
        ),
        safe
    )


def delete_dnat_rule(dnat_rule, chain=PREROUTING_DNAT):
    """Deletes dnat rule from a given chain.

    :param chain:
        Name of the chain from where to remove the rule. If ``None``, the
        default chain ``PREROUTING_DNAT`` will be picked.
    :type chain:
        ``str``
    :param dnat_rule:
        DNAT rule to remove
    :type dnat_rule:
        ``DNATRule``
    """
    if chain is None:
        chain = PREROUTING_DNAT
    return delete_raw_rule('nat', chain,
                           _DNAT_RULE_PATTERN.format(
                               proto=dnat_rule.proto,
                               _proto=dnat_rule.proto,
                               orig_ip=dnat_rule.orig_ip,
                               orig_port=dnat_rule.orig_port,
                               new_ip=dnat_rule.new_ip,
                               new_port=dnat_rule.new_port,
                           ))


def get_current_dnat_rules(chain=PREROUTING_DNAT):
    """Extract all DNAT rules in chain from iptables.

    :param chain:
        Iptables chain to process. If ``None``, the default chain
        ``PREROUTING_DNAT`` will be picked.
    :type chain:
        ``str``
    :returns:
        ``set([DNATRule])`` -- Set of rules.
    """
    rules = set()
    if chain is None:
        chain = PREROUTING_DNAT
    iptables_cmd = ['iptables', '-t', 'nat', '-S', chain]
    for line in subproc.check_output(iptables_cmd).splitlines():
        match = _DNAT_RULE_RE.match(line.strip())
        if match:
            data = match.groupdict()
            rule = firewall.DNATRule(
                data['proto'],
                data['orig_ip'], int(data['orig_port']),
                data['new_ip'], int(data['new_port'])
            )
            rules.add(rule)

    return rules


def configure_dnat_rules(target, chain=PREROUTING_DNAT):
    """Configures iptables DNAT rules.

    The input to the function is target state - a set of DNAT rules that needs
    to be present.

    The function will sync existing iptables configuration with the target
    state, by adding/removing extra rules.

    :param target:
        Desired set of rules
    :type target:
        ``set([DNATRule])``
    :param chain:
        Iptables chain to process.
    :type chain:
        ``str``
    """
    current = get_current_dnat_rules(chain)

    _LOGGER.info('Current %s DNAT: %s', chain, current)
    _LOGGER.info('Target %s DNAT: %s', chain, target)

    # Sync current and desired state.
    for rule in current - target:
        delete_dnat_rule(rule, chain=chain)
    for rule in target - current:
        add_dnat_rule(rule, chain=chain)


def get_current_passthrough_rules(chain=PREROUTING_PASSTHROUGH):
    """Extract all PassThrough rules from iptables.

    :param chain:
        Iptables chain to process. If ``None``, the default chain
        ``PREROUTING_PASSTHROUGH`` will be picked.
    :type chain:
        ``str``
    :returns:
        ``set([PassThroughRule])`` -- Set of rules.
    """
    rules = set()
    if chain is None:
        chain = PREROUTING_PASSTHROUGH
    iptables_cmd = ['iptables', '-t', 'nat', '-S', chain]
    for line in subproc.check_output(iptables_cmd).splitlines():
        match = _PASSTHROUGH_RULE_RE.match(line.strip())
        if match:
            data = match.groupdict()
            rule = firewall.PassThroughRule(data['src_ip'],
                                            data['dst_ip'])
            rules.add(rule)

    return rules


def configure_passthrough_rules(target, chain=PREROUTING_PASSTHROUGH):
    """Configures iptables PassThrough rules.

    The input to the function is target state - a set of PassThrough rules
    that needs to be present.

    The function will sync existing iptables configuration with the target
    state, by adding/removing extra rules.

    :param target:
        Desired set of rules
    :type target:
        ``set([PassThroughRule])``
    :param chain:
        Name of the chain to process.
    :type chain:
        ``str``
    """
    current = get_current_passthrough_rules(chain)

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

    :param passthrough_rule:
        PassThrough rule to insert
    :type passthrough_rule:
        ``PassThroughRule``
    :param chain:
        Name of the chain where to insert the new rule.
    :type chain:
        ``str``
    :param safe:
        Query iptables prior to adding to prevent duplicates
    :param safe:
        ``bool``
    """
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

    :param passthrough_rule:
        PassThrough rule to delete
    :type passthrough_rule:
        ``PassThroughRule``
    :param chain:
        Name of the chain where to remove the rule from.
    :type chain:
        ``str``
    """
    delete_raw_rule(
        'nat', chain,
        _PASSTHROUGH_RULE_PATTERN.format(
            src_ip=passthrough_rule.src_ip,
            dst_ip=passthrough_rule.dst_ip,
        )
    )


def flush_conntrack_table(vip):
    """Clear any entry in the conntrack table for a given VIP.

    This should be run after all the forwarding rules have been removed but
    *before* the VIP is reused.

    :param ``str`` vip:
        IP to scrub from the conntrack table.
    """
    # This addresses the case for UDP session in particular.
    #
    # Since netfilter keeps connection state cache for 30 sec by default, udp
    # packets will not be routed if the same rule is recreated, rather they
    # will be routed to non previously associated container.
    #
    # Deleting connection state will ensure that netfilter connection tracking
    # works correctly.
    try:
        subproc.check_call(['conntrack', '-D', '-g', vip])
    except subprocess.CalledProcessError as exc:
        # return code is 0 if entries were deleted, 1 if no matching
        # entries were found.
        if exc.returncode in (0, 1):
            pass
        else:
            raise


def add_rule(rule, chain=None):
    """Adds a rule to a given chain.

    :param rule:
        Rule to add
    :type rule:
        ``DNATRule``||``PassThroughRule``
    :param chain:
        Name of the chain where to insert the new rule. If set to None
        (default), the default chain will be picked based on the rule type.
    :type chain:
        ``str``
    """
    if isinstance(rule, firewall.DNATRule):
        if chain is not None:
            add_dnat_rule(rule, chain=chain)
        else:
            add_dnat_rule(rule)

    elif isinstance(rule, firewall.PassThroughRule):
        if chain is not None:
            add_passthrough_rule(rule, chain=chain)
        else:
            add_passthrough_rule(rule)
    else:
        raise ValueError("Unknown rule type %r" % (type(rule)))


def delete_rule(rule, chain=None):
    """Delete a rule from a given chain.

    :param rule:
        Rule to remove
    :type rule:
        ``DNATRule``||``PassThroughRule``
    :param chain:
        Name of the chain from which to remove the new rule. If set to None
        (default), the default chain will be picked based on the rule type.
    :type chain:
        ``str``
    """
    if isinstance(rule, firewall.DNATRule):
        if chain is not None:
            delete_dnat_rule(rule, chain=chain)
        else:
            delete_dnat_rule(rule)

    elif isinstance(rule, firewall.PassThroughRule):
        if chain is not None:
            delete_passthrough_rule(rule, chain=chain)
        else:
            delete_passthrough_rule(rule)

    else:
        raise ValueError("Unknown rule type %r" % (type(rule)))


def configure_rules(target):
    """Configures iptables rules.

    The input to the function is target state - a list of rules that needs to
    be present.

    The function will sync existing iptables configuration with the target
    state, by adding/removing extra rules.

    :param target:
        Desired set of rules
    :type target:
        ``set([])``
    """
    dnat_rules = set([rule for rule in target
                      if isinstance(rule, firewall.DNATRule)])
    passthrough_rules = set([rule for rule in target
                             if isinstance(rule, firewall.PassThroughRule)])

    unknown_rules = target - (dnat_rules | passthrough_rules)
    if unknown_rules:
        raise ValueError("Unknown rules %r" % (unknown_rules, ))

    configure_dnat_rules(dnat_rules)
    configure_passthrough_rules(passthrough_rules)


def add_mark_rule(src_ip, environment):
    """Add an environment mark for all traffic coming from an IP.

    :param src_ip:
        Source IP to be marked
    :type src_ip:
        ``str``
    :param environment:
        Environment to use for the mark
    :type environment:
        ``str``
    """
    assert environment in _SET_BY_ENVIRONMENT, \
        "Unknown environment: %r" % environment

    target_set = _SET_BY_ENVIRONMENT[environment]
    add_ip_set(target_set, src_ip)

    # Check that the IP is not marked in any other environment
    other_env_sets = {
        env_set for env_set in _SET_BY_ENVIRONMENT.values()
        if env_set != target_set
    }
    for other_set in other_env_sets:
        if test_ip_set(other_set, src_ip) is True:
            raise Exception('%r is already in %r', src_ip, other_set)


def delete_mark_rule(src_ip, environment):
    """Remove an environment mark from a source IP.

    :param src_ip:
        Source IP on which the mark is set.
    :type src_ip:
        ``str``
    :param environment:
        Environment to use for the mark
    :type environment:
        ``str``
    """
    assert environment in _SET_BY_ENVIRONMENT, \
        "Unknown environment: %r" % environment

    target_set = _SET_BY_ENVIRONMENT[environment]
    rm_ip_set(target_set, src_ip)


def init_set(new_set, **set_options):
    """Create/Initialize a new IPSet set

    :param new_set:
        Name of the IPSet set
    :type new_set:
        ``str``
    :param set_options:
        Extra options for the set creation
    :type set_options:
        Keyword arguments
    """
    _ipset('create', new_set, 'hash:ip',
           # Below expands to a list of k, v, one after the other
           *[str(i) for item in set_options.items() for i in item])
    _ipset('flush', new_set)


def destroy_set(target_set):
    """Destroy an IPSet set.

    :param target_set:
        Name of the IPSet set to destroy.
    :type target_set:
        ``str``
    """
    _ipset('destroy', target_set)


def test_ip_set(target_set, test_ip):
    """Check persence of an IP in an IPSet set

    :param target_set:
        Name of the IPSet set to check.
    :type target_set:
        ``str``
    :param test_ip:
        IP address or host to check.
    :type test_ip:
        ``str``
    :returns ``bool``:
        Returns ``True`` if the IP is in the set, ``False`` otherwise.
    """
    res = _ipset(
        'test', target_set, test_ip,
        use_except=False
    )
    return bool(res == 0)


def add_ip_set(target_set, add_ip):
    """Add an IP to an IPSet set

    :param target_set:
        Name of the IPSet set where to add the IP.
    :type target_set:
        ``str``
    :param add_ip:
        IP address or host to add to the set
    :type add_ip:
        ``str``
    """
    _ipset('add', target_set, add_ip)


def rm_ip_set(target_set, del_ip):
    """Remove an IP from an IPSet set

    :param target_set:
        Name of the IPSet set where to add the IP.
    :type target_set:
        ``str``
    :param del_ip:
        IP address or host to remove from the set
    :type del_ip:
        ``str``
    """
    _ipset('del', target_set, del_ip)


def swap_set(from_set, to_set):
    """Swap to IPSet sets

    :param from_set:
        Name of the source IPSet set
    :type from_set:
        ``str``
    :param to_set:
        Name of the destination IPSet set.
    :type to_set:
        ``str``
    """
    _ipset('swap', from_set, to_set)


def ipset_restore(ipset_state):
    """Initializes the IPSet state.

    :param ipset_state:
        Target state for IPSet (using `ipset save` syntax)
    :type ipset_state:
        ``str``
    """
    _ipset('restore', cmd_input=ipset_state)


def _ipset(*args, **kwargs):
    """Invoke the IPSet command"""
    # Default to using exceptions.
    kwargs.setdefault('use_except', True)
    full_cmd = ['ipset', '-exist'] + list(args)
    return subproc.invoke(full_cmd, **kwargs)


def _iptables_restore(iptables_state, noflush=False):
    """Call iptable-restore with the provide tables dump

    :param iptables_state:
        Table initialization to pass to iptables-restore
    :type iptables_state:
        ``str``
    :param noflush:
        *optional* Do not flush the table before loading the rules.
    :type noflush:
        ``bool``
    """
    # Use logical name (iptables_restore) of the real command.
    cmd = ['iptables_restore']
    if noflush:
        cmd.append('--noflush')

    subproc.invoke(cmd,
                   cmd_input=iptables_state,
                   use_except=True)
