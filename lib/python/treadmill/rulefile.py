"""Functions for handling the network rules directory files.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import logging
import os
import re

from treadmill import firewall


_LOGGER = logging.getLogger(__name__)

_DNAT_FILE_PATTERN = (
    '{chain}:dnat:'
    '{proto}:{src_ip}:{src_port}:{dst_ip}:{dst_port}-{new_ip}:{new_port}'
)

_SNAT_FILE_PATTERN = (
    '{chain}:snat:'
    '{proto}:{src_ip}:{src_port}:{dst_ip}:{dst_port}-{new_ip}:{new_port}'
)

_PASSTHROUGH_FILE_PATTERN = '{chain}:passthrough:{src_ip}-{dst_ip}'

_ANY = '*'

_DNAT_FILE_RE = re.compile((
    r'^' +
    _DNAT_FILE_PATTERN.format(
        # chain
        chain=r'(?P<chain>(?:\w{2,32}))',
        # Protocol
        proto=r'(?P<proto>(?:tcp|udp))',
        # Original source IP
        src_ip=r'(?P<src_ip>(?:(?:\d{1,3}\.){3}\d{1,3}|[*]))',
        # Original source port
        src_port=r'(?P<src_port>(?:\d{1,5}|[*]))',
        # Original destination IP
        dst_ip=r'(?P<dst_ip>(?:(?:\d{1,3}\.){3}\d{1,3}|[*]))',
        # Original destination port
        dst_port=r'(?P<dst_port>(?:\d{1,5}|[*]))',
        # New IP
        new_ip=r'(?P<new_ip>(?:\d{1,3}\.){3}\d{1,3})',
        # New port
        new_port=r'(?P<new_port>\d{1,5})',
    ) +
    r'$'
))

_SNAT_FILE_RE = re.compile((
    r'^' +
    _SNAT_FILE_PATTERN.format(
        # chain
        chain=r'(?P<chain>(?:\w{2,32}))',
        # Protocol
        proto=r'(?P<proto>(?:tcp|udp))',
        # Original source IP
        src_ip=r'(?P<src_ip>(?:(?:\d{1,3}\.){3}\d{1,3}|[*]))',
        # Original source port
        src_port=r'(?P<src_port>(?:\d{1,5}|[*]))',
        # Original destination IP
        dst_ip=r'(?P<dst_ip>(?:(?:\d{1,3}\.){3}\d{1,3}|[*]))',
        # Original destination port
        dst_port=r'(?P<dst_port>(?:\d{1,5}|[*]))',
        # New IP
        new_ip=r'(?P<new_ip>(?:\d{1,3}\.){3}\d{1,3})',
        # New port
        new_port=r'(?P<new_port>\d{1,5})',
    ) +
    r'$'
))

_PASSTHROUGH_FILE_RE = re.compile((
    r'^' +
    _PASSTHROUGH_FILE_PATTERN.format(
        # chain
        chain=r'(?P<chain>(?:\w{2,32}))',
        # Source IP
        src_ip=r'(?P<src_ip>(?:\d{1,3}\.){3}\d{1,3})',
        # Destination IP
        dst_ip=r'(?P<dst_ip>(?:\d{1,3}\.){3}\d{1,3})',
    ) +
    r'$'
))


class RuleMgr:
    """Network rule manager.

    :param ``str`` base_path:
        Base directory that will contain all the rule files
    :param ``str`` owner_path:
        Base directory that will contain all the rule owners.
    """
    __slots__ = (
        '_base_path',
        '_owner_path',
    )

    def __init__(self, base_path, owner_path):
        self._base_path = os.path.realpath(base_path)
        self._owner_path = os.path.realpath(owner_path)

    def _list_rules(self):
        """Return collection of existing rules.
        """
        try:
            return os.listdir(self._base_path)
        except OSError as err:
            if err.errno == errno.ENOENT:
                _LOGGER.warning('Network rule dir %r does not exist.',
                                self._base_path)
                return []
            else:
                raise

    def initialize(self):
        """Initialize the network folder."""
        for rule in self._list_rules():
            os.unlink(os.path.join(self._base_path, rule))

    @property
    def path(self):
        """Currently managed rules directory.

        :returns:
            ``str`` -- Rules directory.
        """
        return self._base_path

    @staticmethod
    def get_rule(rulespec):
        """Parse a forwarding rule spec into a usable firewall rule.

        :param ``str`` rulespec:
            Forward rule in string form
        :returns:
            tuple(Chain, ``DNATRule`` | ``SNATRule`` | ``PassThroughRule``) |
            ``None`` -- A tuple of a chain and a firewall rule object. If
            parsing failed, returns ``None``
        """
        match = _DNAT_FILE_RE.match(rulespec)
        if match:
            data = match.groupdict()
            return (
                data['chain'],
                firewall.DNATRule(
                    proto=data['proto'],
                    src_ip=(
                        data['src_ip'] if data['src_ip'] != _ANY else None
                    ),
                    src_port=(
                        data['src_port'] if data['src_port'] != _ANY else None
                    ),
                    dst_ip=(
                        data['dst_ip'] if data['dst_ip'] != _ANY else None
                    ),
                    dst_port=(
                        data['dst_port'] if data['dst_port'] != _ANY else None
                    ),
                    new_ip=data['new_ip'],
                    new_port=data['new_port']
                )
            )

        match = _SNAT_FILE_RE.match(rulespec)
        if match:
            data = match.groupdict()
            return (
                data['chain'],
                firewall.SNATRule(
                    proto=data['proto'],
                    src_ip=(
                        data['src_ip'] if data['src_ip'] != _ANY else None
                    ),
                    src_port=(
                        data['src_port'] if data['src_port'] != _ANY else None
                    ),
                    dst_ip=(
                        data['dst_ip'] if data['dst_ip'] != _ANY else None
                    ),
                    dst_port=(
                        data['dst_port'] if data['dst_port'] != _ANY else None
                    ),
                    new_ip=data['new_ip'],
                    new_port=data['new_port']
                )
            )

        match = _PASSTHROUGH_FILE_RE.match(rulespec)
        if match:
            data = match.groupdict()
            return (
                data['chain'],
                firewall.PassThroughRule(data['src_ip'],
                                         data['dst_ip'])
            )

        return None

    def get_rules(self):
        """Scrapes the network directory for redirect files.

        :returns:
            ``set`` -- Set of chain/rule tuples in the rules directory
        """
        rules = set()

        for entry in self._list_rules():
            chain_rule = self.get_rule(entry)
            if chain_rule is not None:
                rules.add(chain_rule)
            else:
                _LOGGER.warning('Ignoring unparseable file %r', entry)

        return rules

    def create_rule(self, chain, rule, owner):
        """Creates a symlink who's name represents the port redirection.

        :param ``str`` chain:
            Firewall chain where to insert the rule
        :param ``DNATRule`` | ``SNATRule`` | ``PassThroughRule`` rule:
            Firewall Rule
        :param ``str`` owner:
            Unique container ID of the owner of the rule
        """
        filename = self._filenameify(chain, rule)
        rule_file = os.path.join(self._base_path, filename)
        owner_file = os.path.join(self._owner_path, owner)
        try:
            os.symlink(
                os.path.relpath(owner_file, self._base_path),
                rule_file
            )
            _LOGGER.info('Created %r for %r', filename, owner)

        except OSError as err:
            if err.errno == errno.EEXIST:
                existing_owner = os.path.basename(os.readlink(rule_file))
                if existing_owner != owner:
                    raise
            else:
                raise

    def unlink_rule(self, chain, rule, owner):
        """Unlinks the empty file who's name represents the port redirection.

        :param ``str`` chain:
            Firewall chain where to insert the rule
        :param ``DNATRule`` | ``SNATRule`` | ``PassThroughRule`` rule:
            Firewall Rule
        :param ``str`` owner:
            Unique container ID of the owner of the rule
        """
        filename = self._filenameify(chain, rule)
        rule_file = os.path.join(self._base_path, filename)
        try:
            existing_owner = os.path.basename(os.readlink(rule_file))
            if existing_owner != owner:
                _LOGGER.critical('%r tried to free %r that it does not own',
                                 owner, filename)
                return
            os.unlink(rule_file)
            _LOGGER.debug('Removed %r', filename)

        except OSError as err:
            if err.errno == errno.ENOENT:
                _LOGGER.info('Network rule %r does not exist.', rule_file)
            else:
                _LOGGER.exception('Unable to remove network rule: %r',
                                  rule_file)
                raise

    def garbage_collect(self):
        """Garbage collect all rules without owner.
        """
        for rule in self._list_rules():
            link = os.path.join(self._base_path, rule)
            try:
                os.stat(link)

            except OSError as err:
                if err.errno == errno.ENOENT:
                    _LOGGER.warning('Reclaimed: %r', rule)
                    try:
                        os.unlink(link)
                    except OSError as err:
                        if err.errno == errno.ENOENT:
                            pass
                        else:
                            raise
                else:
                    raise

    @staticmethod
    def _filenameify(chain, rule):
        """Format the rule using rule patterns

        :param ``str`` chain:
            Firewall chain where to insert the rule
        :param ``DNATRule`` | ``SNATRule`` | ``PassThroughRule`` rule:
            Firewall Rule
        :returns:
            ``str`` -- Filename representation of the rule
        """
        if isinstance(rule, firewall.DNATRule):
            return _DNAT_FILE_PATTERN.format(
                chain=chain,
                proto=rule.proto,
                src_ip=(
                    _ANY if rule.src_ip is firewall.ANY_IP else rule.src_ip
                ),
                src_port=(rule.src_port or _ANY),
                dst_ip=(
                    _ANY if rule.dst_ip is firewall.ANY_IP else rule.dst_ip
                ),
                dst_port=(rule.dst_port or _ANY),
                new_ip=rule.new_ip,
                new_port=rule.new_port,
            )
        elif isinstance(rule, firewall.SNATRule):
            return _SNAT_FILE_PATTERN.format(
                chain=chain,
                proto=rule.proto,
                src_ip=(
                    '*' if rule.src_ip is firewall.ANY_IP else rule.src_ip
                ),
                src_port=(rule.src_port or _ANY),
                dst_ip=(
                    '*' if rule.dst_ip is firewall.ANY_IP else rule.dst_ip
                ),
                dst_port=(rule.dst_port or _ANY),
                new_ip=rule.new_ip,
                new_port=rule.new_port,
            )
        elif isinstance(rule, firewall.PassThroughRule):
            return _PASSTHROUGH_FILE_PATTERN.format(
                chain=chain,
                src_ip=rule.src_ip,
                dst_ip=rule.dst_ip,
            )
        else:
            raise ValueError('Invalid rule: %r' % (rule, ))
