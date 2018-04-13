"""Monkey-patch the evaluate_filter_node method of ldap3's MockBaseStrategy.

This function is extracted from ldap3 with a small change in the
`node.tag == MATCH_SUBSTRING` branch. See:
ldap3/strategy/mockBase.py line 822 for ldap3 version 2.3
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import re

from ldap3.strategy import mockBase
from ldap3.strategy.mockBase import (
    to_unicode, log, log_enabled, ERROR, LDAPDefinitionError,
    SERVER_ENCODING,
    ROOT, AND, OR, NOT, MATCH_APPROX,
    MATCH_GREATER_OR_EQUAL, MATCH_LESS_OR_EQUAL, MATCH_EXTENSIBLE,
    MATCH_PRESENT, MATCH_SUBSTRING, MATCH_EQUAL
)


def monkey_patch():
    """Perform the monkey patching."""
    mockBase.MockBaseStrategy.evaluate_filter_node = evaluate_filter_node


# The patched function from ldap3 doesn't follow our conventions
# pylint: disable=too-many-nested-blocks
# pylint: disable=too-many-branches
# pylint: disable=too-many-statements

def evaluate_filter_node(self, node, candidates):
    """After evaluation each 2 sets are added to each MATCH node, one for the
    matched object and one for unmatched object. The unmatched object set is
    needed if a superior node is a NOT that reverts the evaluation. The BOOLEAN
    nodes mix the sets returned by the MATCH nodes"""
    node.matched = set()
    node.unmatched = set()

    if node.elements:
        for element in node.elements:
            self.evaluate_filter_node(element, candidates)

    if node.tag == ROOT:
        return node.elements[0].matched
    elif node.tag == AND:
        for element in node.elements:
            if not node.matched:
                node.matched.update(element.matched)
            else:
                node.matched.intersection_update(element.matched)
            if not node.unmatched:
                node.unmatched.update(element.unmatched)
            else:
                node.unmatched.intersection_update(element.unmatched)
    elif node.tag == OR:
        for element in node.elements:
            node.matched.update(element.matched)
            node.unmatched.update(element.unmatched)
    elif node.tag == NOT:
        node.matched = node.elements[0].unmatched
        node.unmatched = node.elements[0].matched
    elif node.tag == MATCH_GREATER_OR_EQUAL:
        attr_name = node.assertion['attr']
        attr_value = node.assertion['value']
        for candidate in candidates:
            if attr_name in self.connection.server.dit[candidate]:
                for value in self.connection.server.dit[candidate][attr_name]:
                    if value.isdigit() and attr_value.isdigit():
                        if int(value) >= int(attr_value):
                            node.matched.add(candidate)
                        else:
                            node.unmatched.add(candidate)
                    else:
                        if to_unicode(
                                value, SERVER_ENCODING
                        ).lower() >= to_unicode(
                            attr_value, SERVER_ENCODING
                        ).lower():  # case insensitive string comparison
                            node.matched.add(candidate)
                        else:
                            node.unmatched.add(candidate)
    elif node.tag == MATCH_LESS_OR_EQUAL:
        attr_name = node.assertion['attr']
        attr_value = node.assertion['value']
        for candidate in candidates:
            if attr_name in self.connection.server.dit[candidate]:
                for value in self.connection.server.dit[candidate][attr_name]:
                    if value.isdigit() and attr_value.isdigit():
                        if int(value) <= int(attr_value):
                            node.matched.add(candidate)
                        else:
                            node.unmatched.add(candidate)
                    else:
                        if to_unicode(
                                value, SERVER_ENCODING
                        ).lower() <= to_unicode(
                            attr_value, SERVER_ENCODING
                        ).lower():  # case insentive string comparison
                            node.matched.add(candidate)
                        else:
                            node.unmatched.add(candidate)
    elif node.tag == MATCH_EXTENSIBLE:
        self.connection.last_error =\
            'Extensible match not allowed in Mock strategy'
        if log_enabled(ERROR):
            log(ERROR, '<%s> for <%s>',
                self.connection.last_error, self.connection)
        raise LDAPDefinitionError(self.connection.last_error)
    elif node.tag == MATCH_PRESENT:
        attr_name = node.assertion['attr']
        for candidate in candidates:
            if attr_name in self.connection.server.dit[candidate]:
                node.matched.add(candidate)
            else:
                node.unmatched.add(candidate)
    elif node.tag == MATCH_SUBSTRING:
        attr_name = node.assertion['attr']
        # rebuild the original substring filter
        if 'initial' in node.assertion and\
                node.assertion['initial'] is not None:
            substring_filter = re.escape(
                to_unicode(node.assertion['initial'], SERVER_ENCODING)
            )
        else:
            substring_filter = ''

        if 'any' in node.assertion and node.assertion['any'] is not None:
            for middle in node.assertion['any']:
                substring_filter += '.*' + re.escape(
                    to_unicode(middle, SERVER_ENCODING)
                )

        if 'final' in node.assertion and node.assertion['final'] is not None:
            substring_filter += '.*' + re.escape(
                to_unicode(node.assertion['final'], SERVER_ENCODING)
            )

        # This is the patched condition:
        # node.assertion['any'] => node.assertion.get('any', None)
        if substring_filter and not node.assertion.get('any', None) and not\
                node.assertion.get('final', None):  # only initial, adds .*
            substring_filter += '.*'

        regex_filter = re.compile(
            substring_filter, flags=re.UNICODE | re.IGNORECASE
        )  # unicode AND ignorecase
        for candidate in candidates:
            if attr_name in self.connection.server.dit[candidate]:
                for value in self.connection.server.dit[candidate][attr_name]:
                    if regex_filter.match(to_unicode(value, SERVER_ENCODING)):
                        node.matched.add(candidate)
                    else:
                        node.unmatched.add(candidate)
            else:
                node.unmatched.add(candidate)
    elif node.tag == MATCH_EQUAL or node.tag == MATCH_APPROX:
        attr_name = node.assertion['attr']
        attr_value = node.assertion['value']
        for candidate in candidates:
            if attr_name in self.connection.server.dit[candidate] and\
                    self.equal(candidate, attr_name, attr_value):
                node.matched.add(candidate)
            else:
                node.unmatched.add(candidate)
    return None
