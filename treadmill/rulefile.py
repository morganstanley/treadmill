"""Functions for handling the network rules directory files"""


import errno

import logging
import os
import re

from . import firewall
from . import fs


_LOGGER = logging.getLogger(__name__)

_DNAT_FILE_PATTERN = 'dnat:{proto}:{orig_ip}:{orig_port}-{new_ip}:{new_port}'

_PASSTHROUGH_FILE_PATTERN = 'passthrough:{src_ip}-{dst_ip}'

_DNAT_FILE_RE = re.compile((
    r'^' +
    _DNAT_FILE_PATTERN.format(
        # Protocol
        proto=r'(?P<proto>(?:tcp|udp))',
        # Original IP
        orig_ip=r'(?P<orig_ip>(?:\d{1,3}\.){3}\d{1,3})',
        # Original port
        orig_port=r'(?P<orig_port>\d{1,5})',
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
        # Source IP
        src_ip=r'(?P<src_ip>(?:\d{1,3}\.){3}\d{1,3})',
        # Destination IP
        dst_ip=r'(?P<dst_ip>(?:\d{1,3}\.){3}\d{1,3})',
    ) +
    r'$'
))


class RuleMgr(object):
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
        # Make sure rules directory exists.
        fs.mkdir_safe(base_path)
        self._base_path = os.path.realpath(base_path)
        self._owner_path = os.path.realpath(owner_path)

    def initialize(self):
        """Initialize the network folder."""
        for rule in os.listdir(self._base_path):
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
            ``DNATRule``|``PassThroughRule`` | ``None`` -- A tuple of the table
            and the parsed rule. If parsing failed, returns ``None``
        """
        match = _DNAT_FILE_RE.match(rulespec)
        if match:
            data = match.groupdict()
            return firewall.DNATRule(data['proto'],
                                     data['orig_ip'], int(data['orig_port']),
                                     data['new_ip'], int(data['new_port']))

        match = _PASSTHROUGH_FILE_RE.match(rulespec)
        if match:
            data = match.groupdict()
            return firewall.PassThroughRule(data['src_ip'],
                                            data['dst_ip'])

        return None

    def get_rules(self):
        """Scrapes the network directory for redirect files.

        :returns:
            ``set`` -- Set of rules in the rules directory
        """
        rules = set()

        for entry in os.listdir(self._base_path):
            rule = self.get_rule(entry)
            if rule:
                rules.add(rule)
            else:
                _LOGGER.warning("Ignoring unparseable file %r", entry)

        return rules

    def create_rule(self, rule, owner):
        """Creates a symlink who's name represents the port redirection.

        :param ``DNATRule | PassThroughRule`` rule:
            Firewall Rule
        :param ``str`` owner:
            Unique container ID of the owner of the rule
        """
        filename = self._filenameify(rule)
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

    def unlink_rule(self, rule, owner):
        """Unlinks the empty file who's name represents the port redirection.

        :param ``DNATRule | PassThroughRule`` rule:
            Firewall Rule
        :param ``str`` owner:
            Unique container ID of the owner of the rule
        """
        filename = self._filenameify(rule)
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
        for rule in os.listdir(self._base_path):
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
    def _filenameify(rule):
        """Format the rule using rule patterns

        :param ``DNATRule | PassThroughRule`` rule:
            Firewall Rule
        :returns:
            ``str`` -- Filename representation of the rule
        """
        if isinstance(rule, firewall.DNATRule):
            return _DNAT_FILE_PATTERN.format(
                proto=rule.proto,
                orig_ip=rule.orig_ip,
                orig_port=rule.orig_port,
                new_ip=rule.new_ip,
                new_port=rule.new_port,
            )
        elif isinstance(rule, firewall.PassThroughRule):
            return _PASSTHROUGH_FILE_PATTERN.format(
                src_ip=rule.src_ip,
                dst_ip=rule.dst_ip,
            )
        else:
            raise ValueError("Invalid rule: %r" % (rule, ))
