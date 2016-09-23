"""Firewall rule representation"""

from __future__ import absolute_import

import collections


# R0903: Too few public methods
# W0232: No __init__
# E1001: This is not an oldstyle class
# pylint: disable=W0232,R0903,E1001
class DNATRule(collections.namedtuple('DNATRule',
                                      'orig_ip orig_port new_ip new_port')):
    """Definition of a DNAT Rule

    :param orig_ip:
        Original destination IP to be rewriten.
    :type orig_ip:
        ``str``
    :param orig_port:
        Original destination prot to be rewriten.
    :type orig_port:
        ``str``
    :param new_ip:
        New destination IP.
    :type new_ip:
        ``str``
    :param new_port:
        New destination port.
    :type new_port:
        ``str``
    """
    __slots__ = ()


# R0903: Too few public methods
# W0232: No __init__
# E1001: This is not an oldstyle class
# pylint: disable=W0232,R0903,E1001
class PassThroughRule(collections.namedtuple('PassThroughRule',
                                             'src_ip dst_ip')):
    """Definition of a PassThrough rule

    :param src_ip:
        Source IP address for which to set the passthrough
    :type src_ip:
        ``str``
    :param dst_ip:
        Destination IP address for which to set the passthrough
    :type dst_ip:
        ``str``
    """
    __slots__ = ()
