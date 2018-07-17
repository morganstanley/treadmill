"""Firewall rule representation.
"""


from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from __future__ import absolute_import

ANY_IP = '0.0.0.0/0'
ANY_PORT = 0


class DNATRule:
    """Definition of a DNAT Rule

    :param ``str`` new_dst_ip:
        New destination IP.
    :param ``int`` new_dst_port:
        New destination port.
    :param ``str`` proto:
        Proto for the redirection
    :param ``str`` src_ip:
        Original source IP.
    :param ``int`` src_port:
        Original source port.
    :param ``str`` dst_ip:
        Original destination IP to be rewriten.
    :param ``int`` dst_port:
        Original destination port to be rewriten.
    """
    __slots__ = (
        'proto',
        'dst_ip',
        'dst_port',
        'src_ip',
        'src_port',
        'new_ip',
        'new_port',
    )

    def __init__(self, proto, new_ip, new_port,
                 src_ip=ANY_IP, src_port=ANY_PORT,
                 dst_ip=ANY_IP, dst_port=ANY_PORT):
        if src_ip is None:
            src_ip = ANY_IP
        if src_port is None:
            src_port = ANY_PORT
        if dst_ip is None:
            dst_ip = ANY_IP
        if dst_port is None:
            dst_port = ANY_PORT
        self.proto = proto
        self.src_ip = src_ip
        self.src_port = int(src_port)
        self.dst_ip = dst_ip
        self.dst_port = int(dst_port)
        self.new_ip = new_ip
        self.new_port = int(new_port)

    def __repr__(self):
        return (
            '{cls}({proto}:'
            '{src_ip}:{src_port}:{dst_ip}:{dst_port}'
            '->D{new_ip}:{new_port})'
        ).format(
            cls=type(self).__name__,
            proto=self.proto,
            src_ip=('*' if self.src_ip is ANY_IP else self.src_ip),
            src_port=(self.src_port or '*'),
            dst_ip=('*' if self.dst_ip is ANY_IP else self.dst_ip),
            dst_port=(self.dst_port or '*'),
            new_ip=self.new_ip,
            new_port=self.new_port,
        )

    def __eq__(self, other):
        return (
            type(self) is type(other) and
            self.proto == other.proto and
            self.src_ip == other.src_ip and
            self.src_port == other.src_port and
            self.dst_ip == other.dst_ip and
            self.dst_port == other.dst_port and
            self.new_ip == other.new_ip and
            self.new_port == other.new_port
        )

    def __hash__(self):
        return hash(
            (
                type(self),
                self.proto,
                self.src_ip,
                self.src_port,
                self.dst_ip,
                self.dst_port,
                self.new_ip,
                self.new_port,
            )
        )


class SNATRule:
    """Definition of a SNAT Rule

    :param ``str`` new_ip:
        New source IP.
    :param ``str`` new_port:
        New source port.
    :param ``str`` proto:
        Proto for the redirection
    :param ``str`` src_ip:
        Original source IP to be rewriten.
    :param ``int`` src_port:
        Original source port to be rewriten.
    :param ``str`` dst_ip:
        Original destination IP.
    :param ``int`` dst_port:
        Original destination port.
    """
    __slots__ = (
        'proto',
        'dst_ip',
        'dst_port',
        'src_ip',
        'src_port',
        'new_ip',
        'new_port',
    )

    def __init__(self, proto, new_ip, new_port,
                 src_ip=ANY_IP, src_port=ANY_PORT,
                 dst_ip=ANY_IP, dst_port=ANY_PORT):
        if src_ip is None:
            src_ip = ANY_IP
        if src_port is None:
            src_port = ANY_PORT
        if dst_ip is None:
            dst_ip = ANY_IP
        if dst_port is None:
            dst_port = ANY_PORT

        self.proto = proto
        self.src_ip = src_ip
        self.src_port = int(src_port)
        self.dst_ip = dst_ip
        self.dst_port = int(dst_port)
        self.new_ip = new_ip
        self.new_port = int(new_port)

    def __repr__(self):
        return (
            '{cls}({proto}:'
            '{src_ip}:{src_port}:{dst_ip}:{dst_port}'
            '->S{new_ip}:{new_port})'
        ).format(
            cls=type(self).__name__,
            proto=self.proto,
            src_ip=('*' if self.src_ip is ANY_IP else self.src_ip),
            src_port=(self.src_port or '*'),
            dst_ip=('*' if self.dst_ip is ANY_IP else self.dst_ip),
            dst_port=(self.dst_port or '*'),
            new_ip=self.new_ip,
            new_port=self.new_port,
        )

    def __eq__(self, other):
        return (
            type(self) is type(other) and
            self.proto == other.proto and
            self.src_ip == other.src_ip and
            self.src_port == other.src_port and
            self.dst_ip == other.dst_ip and
            self.dst_port == other.dst_port and
            self.new_ip == other.new_ip and
            self.new_port == other.new_port
        )

    def __hash__(self):
        return hash(
            (
                type(self),
                self.proto,
                self.src_ip,
                self.src_port,
                self.dst_ip,
                self.dst_port,
                self.new_ip,
                self.new_port,
            )
        )


# TODO: Fold PassThroughRule a kind of DNAT rule
class PassThroughRule:
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
    __slots__ = (
        'src_ip',
        'dst_ip'
    )

    def __init__(self, src_ip, dst_ip):
        self.src_ip = src_ip
        self.dst_ip = dst_ip

    def __repr__(self):
        return '{cls}({src_ip}->{dst_ip})'.format(
            cls=self.__class__.__name__,
            src_ip=self.src_ip,
            dst_ip=self.dst_ip,
        )

    def __eq__(self, other):
        return (
            type(self) is type(other) and
            self.src_ip == other.src_ip and
            self.dst_ip == other.dst_ip
        )

    def __hash__(self):
        return hash(
            (
                self.src_ip,
                self.dst_ip,
            )
        )
