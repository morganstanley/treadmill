"""Manages Treadmill applications lifecycle.
"""

import logging
import os
import socket

from treadmill import appcfg
from treadmill import cgroups
from treadmill import firewall
from treadmill import fs
from treadmill import iptables
from treadmill import newnet
from treadmill import runtime
from treadmill import supervisor
from treadmill import utils

from treadmill.syscall import unshare

from . import image


_LOGGER = logging.getLogger(__name__)


def run(tm_env, container_dir, manifest, watchdog, terminated):
    """Creates container environment and prepares to exec root supervisor.
    """
    _LOGGER.info('Running %r', container_dir)

    # Apply memory limits first thing, so that app_run does not consume memory
    # from treadmill/core.
    _apply_cgroup_limits(tm_env, container_dir, manifest)

    img_impl = image.get_image(tm_env, manifest)

    unique_name = appcfg.manifest_unique_name(manifest)
    # First wait for the network device to be ready
    network_client = tm_env.svc_network.make_client(
        os.path.join(container_dir, 'network')
    )
    app_network = network_client.wait(unique_name)

    manifest['network'] = app_network
    # FIXME: backward compatibility for TM 2.0. Remove in 3.0
    manifest['vip'] = {
        'ip0': app_network['gateway'],
        'ip1': app_network['vip'],
    }

    # Allocate dynamic ports
    #
    # Ports are taken from ephemeral range, by binding to socket to port 0.
    #
    # Sockets are then put into global list, so that they are not closed
    # at gc time, and address remains in use for the lifetime of the
    # supervisor.
    sockets = runtime.allocate_network_ports(
        app_network['external_ip'], manifest
    )

    app = runtime.save_app(manifest, container_dir)

    if not app.shared_network:
        _unshare_network(tm_env, app)

    # Create root directory structure (chroot base).
    # container_dir/<subdir>
    root_dir = os.path.join(container_dir, 'root')

    # Create and format the container root volume.
    _create_root_dir(tm_env, container_dir, root_dir, app)

    # NOTE: below here, MOUNT namespace is private

    # Unpack the image to the root directory.
    img_impl.unpack(container_dir, root_dir, app)

    # If network is shared, close sockets before starting the
    # supervisor, as these ports will be use be container apps.
    if app.shared_network:
        for socket_ in sockets:
            socket_.close()

    watchdog.remove()

    if not terminated:
        sys_dir = os.path.join(container_dir, 'sys')
        supervisor.exec_root_supervisor(sys_dir)


def _apply_cgroup_limits(tm_env, container_dir, manifest):
    """Configures cgroups and limits.

    :param tm_env:
        Treadmill application environment
    :type tm_env:
        `appenv.AppEnvironment`
    :param container_dir:
        Full path to the container
    :type container_dir:
        ``str``
    :param manifest:
        App manifest.
    :type manifest:
        ``dict``
    """
    app = utils.to_obj(manifest)

    # Generate a unique name for the app
    unique_name = appcfg.app_unique_name(app)

    # Setup the service clients
    cgroup_client = tm_env.svc_cgroup.make_client(
        os.path.join(container_dir, 'cgroups')
    )
    localdisk_client = tm_env.svc_localdisk.make_client(
        os.path.join(container_dir, 'localdisk')
    )
    network_client = tm_env.svc_network.make_client(
        os.path.join(container_dir, 'network')
    )

    # Cgroup
    cgroup_req = {
        'memory': app.memory,
        'cpu': app.cpu,
    }
    # Local Disk
    localdisk_req = {
        'size': app.disk,
    }
    # Network
    network_req = {
        'environment': app.environment,
    }

    cgroup_client.put(unique_name, cgroup_req)
    localdisk_client.put(unique_name, localdisk_req)

    if not app.shared_network:
        network_client.put(unique_name, network_req)

    app_cgroups = cgroup_client.wait(unique_name)

    _LOGGER.info('Joining cgroups: %r', app_cgroups)
    for subsystem, cgrp in app_cgroups.items():
        cgroups.join(subsystem, cgrp)


def _unshare_network(tm_env, app):
    """Configures private app network.

    :param ``appenv.AppEnvironment`` tm_env:
        Treadmill application environment
    """
    unique_name = appcfg.app_unique_name(app)
    # Configure DNAT rules while on host network.
    for endpoint in app.endpoints:
        _LOGGER.info('Creating DNAT rule: %s:%s -> %s:%s',
                     app.network.external_ip,
                     endpoint.real_port,
                     app.network.vip,
                     endpoint.port)
        dnatrule = firewall.DNATRule(proto=endpoint.proto,
                                     dst_ip=app.network.external_ip,
                                     dst_port=endpoint.real_port,
                                     new_ip=app.network.vip,
                                     new_port=endpoint.port)
        snatrule = firewall.SNATRule(proto=endpoint.proto,
                                     src_ip=app.network.vip,
                                     src_port=endpoint.port,
                                     new_ip=app.network.external_ip,
                                     new_port=endpoint.real_port)
        tm_env.rules.create_rule(chain=iptables.PREROUTING_DNAT,
                                 rule=dnatrule,
                                 owner=unique_name)
        tm_env.rules.create_rule(chain=iptables.POSTROUTING_SNAT,
                                 rule=snatrule,
                                 owner=unique_name)

        # See if this container requires vring service
        if app.vring:
            _LOGGER.debug('adding %r to VRing set', app.network.vip)
            iptables.add_ip_set(
                iptables.SET_VRING_CONTAINERS,
                app.network.vip
            )

        # See if this was an "infra" endpoint and if so add it to the whitelist
        # set.
        if getattr(endpoint, 'type', None) == 'infra':
            _LOGGER.debug('adding %s:%s to infra services set',
                          app.network.vip, endpoint.port)
            iptables.add_ip_set(
                iptables.SET_INFRA_SVC,
                '{ip},{proto}:{port}'.format(
                    ip=app.network.vip,
                    proto=endpoint.proto,
                    port=endpoint.port,
                )
            )

    for port in app.ephemeral_ports.tcp:
        _LOGGER.info('Creating ephemeral DNAT rule: %s:%s -> %s:%s',
                     app.network.external_ip, port,
                     app.network.vip, port)
        dnatrule = firewall.DNATRule(proto='tcp',
                                     dst_ip=app.network.external_ip,
                                     dst_port=port,
                                     new_ip=app.network.vip,
                                     new_port=port)
        tm_env.rules.create_rule(chain=iptables.PREROUTING_DNAT,
                                 rule=dnatrule,
                                 owner=unique_name)
        # Treat ephemeral ports as infra, consistent with current prodperim
        # behavior.
        iptables.add_ip_set(iptables.SET_INFRA_SVC,
                            '{ip},tcp:{port}'.format(ip=app.network.vip,
                                                     port=port))

    for port in app.ephemeral_ports.udp:
        _LOGGER.info('Creating ephemeral DNAT rule: %s:%s -> %s:%s',
                     app.network.external_ip, port,
                     app.network.vip, port)
        dnatrule = firewall.DNATRule(proto='udp',
                                     dst_ip=app.network.external_ip,
                                     dst_port=port,
                                     new_ip=app.network.vip,
                                     new_port=port)
        tm_env.rules.create_rule(chain=iptables.PREROUTING_DNAT,
                                 rule=dnatrule,
                                 owner=unique_name)
        # Treat ephemeral ports as infra, consistent with current prodperim
        # behavior.
        iptables.add_ip_set(iptables.SET_INFRA_SVC,
                            '{ip},udp:{port}'.format(ip=app.network.vip,
                                                     port=port))

    # configure passthrough while on main network.
    if getattr(app, 'passthrough', None):
        _LOGGER.info('adding passthrough for: %r', app.passthrough)
        # Resolve all the hosts (+dedup)
        new_ips = {
            socket.gethostbyname(host)
            for host in app.passthrough
        }

        # Create a passthrough rule from each of the source IP to the
        # container IP and record these source IP in a set.
        for ipaddr in new_ips:
            passthroughrule = firewall.PassThroughRule(
                src_ip=ipaddr,
                dst_ip=app.network.vip,
            )
            tm_env.rules.create_rule(chain=iptables.PREROUTING_PASSTHROUGH,
                                     rule=passthroughrule,
                                     owner=unique_name)

    service_ip = None
    if app.shared_ip:
        service_ip = app.network.external_ip

    # Unshare network and create virtual device
    newnet.create_newnet(app.network.veth,
                         app.network.vip,
                         app.network.gateway,
                         service_ip)


def _create_root_dir(tm_env, container_dir, root_dir, app):
    """Prepares chrooted environment."""
    # Generate a unique name for the app
    unique_name = appcfg.app_unique_name(app)

    # First wait for the block device to be ready
    localdisk_client = tm_env.svc_localdisk.make_client(
        os.path.join(container_dir, 'localdisk')
    )
    localdisk = localdisk_client.wait(unique_name)

    already_initialized = fs.test_filesystem(localdisk['block_dev'])
    if not already_initialized:
        # Format the block device
        fs.create_filesystem(localdisk['block_dev'])

    _LOGGER.info('Creating container root directory: %s', root_dir)
    # Creates directory that will serve as new root.
    fs.mkdir_safe(fs.norm_safe(root_dir))
    # Unshare the mount namespace
    unshare.unshare(unshare.CLONE_NEWNS)
    # Mount the container root volume
    fs.mount_filesystem(localdisk['block_dev'], root_dir)
