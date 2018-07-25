"""Creates new network subsystem with virtual eth device."""


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import os

import logging
import multiprocessing

from . import utils
from . import iptables
from . import netdev
from .syscall import unshare


_LOGGER = logging.getLogger(__name__)


def create_newnet(veth, dev_ip, gateway_ip, service_ip=None):
    """Unshares network subsystem and setup virtual interface in the given
    container network namespace.

    The steps are:

    - Fork a child (child shares original network)
    - Unshare network subsystem namespace
    - Signal to the child that we are ready
    - Child creates virtual eth device and moves one end to the new namespace
    - Child exits

    :param dev_ip:
        IP address of the node side of the virtual interface
    :type dev_ip:
        ``str``
    :param gateway_ip:
        Gateway IP address for the node side of the virtual interface
    :type gateway_ip:
        ``str``
    :param service_ip:
        Service IP address of the host the container is running on. If ``None``
        that indicates not to use the external IP for the container.
    :type service_ip:
        ``str``
    """
    pid = os.getpid()
    unshared_event = multiprocessing.Event()

    childpid = os.fork()
    if childpid:
        # Parent
        try:
            unshare.unshare(unshare.CLONE_NEWNET)
        except OSError:
            _LOGGER.exception('Unable to unshare network subsystem.')
            raise
        finally:
            # prevent child from infinite waiting
            unshared_event.set()

        # Wait for child to exit, and then proceed with finising the setup in
        # the container (self)
        while True:
            try:
                # FIXME(boysson): We need to check the child exited properly
                (_pid, _status) = os.waitpid(childpid, 0)
                break
            except OSError as exc:
                if exc.errno == errno.EINTR:
                    _LOGGER.info('waitpid interrupted, cont.')
                else:
                    _LOGGER.exception('unhandled waitpid exception')
                    raise

        # Past this point, veth0 is in the nodes network namespace and veth is
        # in the container's network namespace (this process).
        # Now that network is unshared, proceed with finishing the setup in the
        # container (this process).
        _configure_veth(veth, dev_ip, gateway_ip, service_ip)

    else:
        # Child - wait for the parent to unshare network subsystem, then
        # proceed with passing the veth into the namespace.
        unshared_event.wait()
        unshared_event = None
        # Move container device into the network namespace of the target
        # process.
        netdev.link_set_netns(veth, pid)
        utils.sys_exit(0)


def _configure_veth(veth, dev_ip, gateway_ip, service_ip=None):
    """Configures the network interface of the container.

    The function should be invoked in the context of unshared network
    subsystem.

    TODO: should we check that ifconfig is empty before proceeding?
    """
    _LOGGER.info('configure container: %s ip = %r(%r), gateway_ip = %r',
                 veth, dev_ip, service_ip, gateway_ip)

    # Bring up loopback
    netdev.link_set_up('lo')

    # Rename the container's interface to 'eth0'
    netdev.link_set_name(veth, 'eth0')

    # Configure ARP on container network device
    netdev.dev_conf_arp_ignore_set(
        'eth0',
        netdev.ARP_IGNORE_DO_NOT_REPLY_ANY_ON_HOST
    )

    # Configure the IP address of the container network device
    if service_ip is not None:
        # Add the service IP first so that it is what we see in ifconfig
        netdev.addr_add(
            '{ip}/32'.format(ip=service_ip),
            'eth0',
            addr_scope='host'
        )
    netdev.addr_add(
        '{ip}/32'.format(ip=dev_ip),
        'eth0',
        addr_scope='link'
    )

    netdev.link_set_up('eth0')

    netdev.route_add(
        gateway_ip,
        devname='eth0',
        route_scope='link'
    )

    if service_ip is None:
        route_src = dev_ip
    else:
        route_src = service_ip

    netdev.route_add(
        'default',
        via=gateway_ip,
        src=route_src,
    )

    iptables.initialize_container()
    if service_ip is not None:
        # Set PRE- and POSTROUTING for the host IP in the container
        iptables.add_raw_rule(
            'nat', 'PREROUTING',
            '-i eth0 -j DNAT --to-destination {service_ip}'.format(
                service_ip=service_ip,
            )
        )
        iptables.add_raw_rule(
            'nat', 'POSTROUTING',
            '-o eth0  -j SNAT --to-source {container_ip}'.format(
                container_ip=dev_ip,
            )
        )
