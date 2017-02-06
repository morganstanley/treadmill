"""Firewall rule representation"""


class DNATRule(object):
    """Definition of a DNAT Rule

    :param proto:
        Proto for the redirection
    :type proto:
        ``str``
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
    __slots__ = (
        'proto',
        'orig_ip',
        'orig_port',
        'new_ip',
        'new_port',
    )

    def __init__(self, proto, orig_ip, orig_port, new_ip, new_port):
        self.proto = proto
        self.orig_ip = orig_ip
        self.orig_port = orig_port
        self.new_ip = new_ip
        self.new_port = new_port

    def __repr__(self):
        return '{cls}({proto}:{origip}:{origport}->{newip}:{newport})'.format(
            cls=self.__class__.__name__,
            proto=self.proto,
            origip=self.orig_ip,
            origport=self.orig_port,
            newip=self.new_ip,
            newport=self.new_port,
        )

    def __eq__(self, other):
        return (
            self.proto == other.proto and
            self.orig_ip == other.orig_ip and
            self.orig_port == other.orig_port and
            self.new_ip == other.new_ip and
            self.new_port == other.new_port
        )

    def __hash__(self):
        return hash(
            (
                self.proto,
                self.orig_ip,
                self.orig_port,
                self.new_ip,
                self.new_port,
            )
        )


class PassThroughRule(object):
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
