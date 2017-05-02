""" Manages Treadmill applications lifecycle."""
from __future__ import absolute_import

import errno
import logging
import os
import pwd
import random
import shutil
import socket
import stat
import tempfile

import yaml

import treadmill

from treadmill import appcfg
from treadmill import cgroups
from treadmill import exc
from treadmill import firewall
from treadmill import fs
from treadmill import iptables
from treadmill import logcontext as lc
from treadmill import newnet
from treadmill import subproc
from treadmill import supervisor
from treadmill import utils


_LOGGER = lc.ContainerAdapter(logging.getLogger(__name__))

_APP_YML = 'app.yml'
_STATE_YML = 'state.yml'


def apply_cgroup_limits(tm_env, container_dir, manifest):
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


def run(tm_env, container_dir, manifest, watchdog, terminated):
    """Creates container environment and prepares to exec root supervisor.

    The function is intended to be invoked from 'run' script and never
    returns.

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
    :param watchdog:
        App run watchdog.
    :type watchdog:
        ``treadmill.watchdog``
    :param terminated:
        Flag where terminated signal will accumulate.
    :param terminated:
        ``set``
    :returns:
        This function never returns
    """

    with lc.LogContext(_LOGGER, os.path.basename(container_dir),
                       lc.ContainerAdapter) as log:
        # R0915: Need to refactor long function into smaller pieces.
        # R0912: Too many branches
        #
        # pylint: disable=R0915,R0912
        log.info('Running %r', container_dir)

        # Allocate dynamic ports
        #
        # Ports are taken from ephemeral range, by binding to socket to port 0.
        #
        # Sockets are then put into global list, so that they are not closed
        # at gc time, and address remains in use for the lifetime of the
        # supervisor.
        sockets = _allocate_network_ports(
            tm_env.host_ip, manifest
        )

        unique_name = appcfg.manifest_unique_name(manifest)
        # First wait for the network device to be ready
        network_client = tm_env.svc_network.make_client(
            os.path.join(container_dir, 'network')
        )
        app_network = network_client.wait(unique_name)

        manifest['network'] = app_network
        # FIXME(boysson): backward compatibility for TM 2.0. Remove in 3.0
        manifest['vip'] = {
            'ip0': app_network['gateway'],
            'ip1': app_network['vip'],
        }

        # Save the manifest with allocated vip and ports in the state
        state_file = os.path.join(container_dir, _STATE_YML)
        with tempfile.NamedTemporaryFile(dir=container_dir,
                                         delete=False) as temp_file:
            yaml.dump(manifest, stream=temp_file)
            # chmod for the file to be world readable.
            os.fchmod(
                temp_file.fileno(),
                stat.S_IWUSR | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
            )
        os.rename(temp_file.name, state_file)

        # Freeze the app data into a namedtuple object
        app = utils.to_obj(manifest)

        if not app.shared_network:
            _unshare_network(tm_env, app)

        # Create root directory structure (chroot base).
        # container_dir/<subdir>
        root_dir = os.path.join(container_dir, 'root')

        # chroot_dir/<subdir>
        # FIXME(boysson): env_dir should be in a well defined location (part
        #                 of the container "API").
        env_dir = os.path.join(root_dir, 'environ')

        # Create and format the container root volumne
        _create_root_dir(tm_env, container_dir, root_dir, app)

        # NOTE: below here, MOUNT namespace is private

        # FIXME(boysson): Lots of things are still reading this file.
        #                 Copy updated state manifest as app.yml in the
        #                 container_dir so it is visible in chrooted env.
        shutil.copy(state_file, os.path.join(root_dir, _APP_YML))
        _create_environ_dir(env_dir, app)
        # Create the supervision tree
        _create_supervision_tree(container_dir, app)

        # Set app limits before chroot.
        _share_cgroup_info(app, root_dir)

        ldpreloads = []
        if app.ephemeral_ports.tcp or app.ephemeral_ports.udp:
            treadmill_bind_preload = subproc.resolve(
                'treadmill_bind_preload.so')
            ldpreloads.append(treadmill_bind_preload)

        _prepare_ldpreload(root_dir, ldpreloads)

        def _bind(src, tgt):
            """Helper function to bind source to target in the same root"""
            # FIXME(boysson): This name mount_bind() have counter-intuitive
            #                 arguments ordering.
            fs.mount_bind(root_dir, tgt,
                          target='%s/%s' % (root_dir, src),
                          bind_opt='--bind')

        # Override the /etc/resolv.conf, so that container always uses
        # dnscache.
        _bind('.etc/resolv.conf', '/etc/resolv.conf')
        _bind('.etc/hosts', '/etc/hosts')

        if ldpreloads:
            # Override /etc/ld.so.preload to enforce necessary system hooks
            _bind('.etc/ld.so.preload', '/etc/ld.so.preload')

        # If network is shared, close ephermal sockets before starting the
        # supervisor, as these ports will be use be container apps.
        if app.shared_network:
            for socket_ in sockets:
                socket_.close()

            # Override pam.d sshd stack with special sshd pam that unshares
            # network.
            _bind('.etc/pam.d/sshd.shared_network', '/etc/pam.d/sshd')
        else:
            # Override pam.d sshd stack.
            _bind('.etc/pam.d/sshd', '/etc/pam.d/sshd')

        watchdog.remove()

        if not terminated:
            sys_dir = os.path.join(container_dir, 'sys')
            supervisor.exec_root_supervisor(sys_dir)


def _unshare_network(tm_env, app):
    """Configures private app network.

    :param ``appenv.AppEnvironment`` tm_env:
        Treadmill application environment
    """
    unique_name = appcfg.app_unique_name(app)
    # Configure DNAT rules while on host network.
    for endpoint in app.endpoints:
        _LOGGER.info('Creating DNAT rule: %s:%s -> %s:%s',
                     tm_env.host_ip,
                     endpoint.real_port,
                     app.network.vip,
                     endpoint.port)
        dnatrule = firewall.DNATRule(proto=endpoint.proto,
                                     dst_ip=tm_env.host_ip,
                                     dst_port=endpoint.real_port,
                                     new_ip=app.network.vip,
                                     new_port=endpoint.port)
        snatrule = firewall.SNATRule(proto=endpoint.proto,
                                     src_ip=app.network.vip,
                                     src_port=endpoint.port,
                                     new_ip=tm_env.host_ip,
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
                     tm_env.host_ip, port,
                     app.network.vip, port)
        dnatrule = firewall.DNATRule(proto='tcp',
                                     dst_ip=tm_env.host_ip,
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
                     tm_env.host_ip, port,
                     app.network.vip, port)
        dnatrule = firewall.DNATRule(proto='udp',
                                     dst_ip=tm_env.host_ip,
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
        service_ip = tm_env.host_ip

    # Unshare network and create virtual device
    newnet.create_newnet(app.network.veth,
                         app.network.vip,
                         app.network.gateway,
                         service_ip)


def _create_environ_dir(env_dir, app):
    """Creates environ dir for s6-envdir."""
    appenv = {envvar.name: envvar.value for envvar in app.environ}
    supervisor.create_environ_dir(
        os.path.join(env_dir, 'app'),
        appenv
    )

    env = {
        'TREADMILL_CPU': app.cpu,
        'TREADMILL_DISK': app.disk,
        'TREADMILL_MEMORY': app.memory,
        'TREADMILL_CELL': app.cell,
        'TREADMILL_APP': app.app,
        'TREADMILL_INSTANCEID': app.task,
        'TREADMILL_HOST_IP': app.host_ip,
        'TREADMILL_IDENTITY': app.identity,
        'TREADMILL_IDENTITY_GROUP': app.identity_group,
        'TREADMILL_PROID': app.proid,
    }

    for endpoint in app.endpoints:
        envname = 'TREADMILL_ENDPOINT_{0}'.format(endpoint.name.upper())
        env[envname] = endpoint.real_port

    env['TREADMILL_EPHEMERAL_TCP_PORTS'] = ' '.join(
        [str(port) for port in app.ephemeral_ports.tcp]
    )
    env['TREADMILL_EPHEMERAL_UDP_PORTS'] = ' '.join(
        [str(port) for port in app.ephemeral_ports.udp]
    )

    env['TREADMILL_CONTAINER_IP'] = app.vip.ip1

    # Override appenv with mandatory treadmill environment.
    supervisor.create_environ_dir(
        os.path.join(env_dir, 'sys'),
        env
    )


def _create_logrun(directory):
    """Creates log directory with run file to start s6 logger."""
    fs.mkdir_safe(os.path.join(directory, 'log'))
    utils.create_script(os.path.join(directory, 'log', 'run'),
                        'logger.run')


def _create_sysrun(sys_dir, name, command, down=False):
    """Create system script."""
    fs.mkdir_safe(os.path.join(sys_dir, name))
    utils.create_script(os.path.join(sys_dir, name, 'run'),
                        'supervisor.run_sys',
                        cmd=command)
    _create_logrun(os.path.join(sys_dir, name))
    if down:
        utils.touch(os.path.join(sys_dir, name, 'down'))


def _create_supervision_tree(container_dir, app):
    """Creates s6 supervision tree."""
    root_dir = os.path.join(container_dir, 'root')

    # Services and sys directories will be restored when container restarts
    # with data retention on existing volume.
    #
    # Sys directories will be removed. Services directory will stay, which
    # present a danger of accumulating restart counters in finished files.
    #
    # TODO:
    #
    # It is rather arbitrary how restart counts should work when data is
    # restored, but most likely services are "restart always" policy, so it
    # will not affect them.
    services_dir = os.path.join(container_dir, 'services')
    sys_dir = os.path.join(container_dir, 'sys')
    if os.path.exists(sys_dir):
        _LOGGER.info('Deleting existing sys dir: %s', sys_dir)
        shutil.rmtree(sys_dir)

    app_yaml = os.path.join(root_dir, 'app.yml')

    # Create /services directory for the supervisor
    svcdir = os.path.join(root_dir, 'services')
    fs.mkdir_safe(svcdir)

    fs.mkdir_safe(services_dir)
    fs.mount_bind(root_dir, '/services', services_dir)

    root_pw = pwd.getpwnam('root')
    proid_pw = pwd.getpwnam(app.proid)

    # Create .s6-svscan directories for svscan finish
    sys_svscandir = os.path.join(sys_dir, '.s6-svscan')
    fs.mkdir_safe(sys_svscandir)

    svc_svscandir = os.path.join(services_dir, '.s6-svscan')
    fs.mkdir_safe(svc_svscandir)

    # svscan finish scripts to wait on all services
    utils.create_script(
        os.path.join(sys_svscandir, 'finish'),
        'svscan.finish',
        timeout=6000
    )

    utils.create_script(
        os.path.join(svc_svscandir, 'finish'),
        'svscan.finish',
        timeout=5000
    )

    for svc in app.services:
        if getattr(svc, 'root', False):
            svc_user = 'root'
            svc_home = root_pw.pw_dir
            svc_shell = root_pw.pw_shell
        else:
            svc_user = app.proid
            svc_home = proid_pw.pw_dir
            svc_shell = proid_pw.pw_shell

        supervisor.create_service(
            services_dir, svc_user, svc_home, svc_shell,
            svc.name, svc.command,
            env=app.environment, down=True,
            envdirs=['/environ/app', '/environ/sys'], as_root=True,
        )
        _create_logrun(os.path.join(services_dir, svc.name))

    for svc in app.system_services:
        supervisor.create_service(
            services_dir, 'root', root_pw.pw_dir, root_pw.pw_shell,
            svc.name, svc.command,
            env=app.environment, down=False,
            envdirs=['/environ/sys'], as_root=True,
        )
        _create_logrun(os.path.join(services_dir, svc.name))

    # Vring services
    for cell in app.vring.cells:
        fs.mkdir_safe(os.path.join(sys_dir, 'vring.%s' % cell))
        cmd = '%s sproc --zookeeper - --cell %s vring %s' % (
            treadmill.TREADMILL_BIN, cell, app_yaml)
        utils.create_script(
            os.path.join(sys_dir, 'vring.%s' % cell, 'run'),
            'supervisor.run_sys',
            cmd=cmd
        )
        _create_logrun(os.path.join(sys_dir, 'vring.%s' % cell))

    # Create endpoint presence service
    presence_monitor_cmd = '%s sproc presence monitor %s %s' % (
        treadmill.TREADMILL_BIN,
        app_yaml,
        container_dir
    )
    presence_register_cmd = '%s sproc presence register %s %s' % (
        treadmill.TREADMILL_BIN,
        app_yaml,
        container_dir
    )
    shadow_etc = os.path.join(container_dir, 'root', '.etc')
    host_aliases_cmd = '%s sproc host-aliases --aliases-dir %s %s %s' % (
        treadmill.TREADMILL_BIN,
        os.path.join(shadow_etc, 'hosts-aliases'),
        os.path.join(shadow_etc, 'hosts.original'),
        os.path.join(shadow_etc, 'hosts'),
    )

    _create_sysrun(sys_dir, 'monitor', presence_monitor_cmd)
    _create_sysrun(sys_dir, 'register', presence_register_cmd)
    _create_sysrun(sys_dir, 'hostaliases', host_aliases_cmd)
    _create_sysrun(
        sys_dir,
        'start_container',
        '%s %s %s -m -p -i s6-svscan /services' % (
            subproc.resolve('chroot'),
            root_dir,
            subproc.resolve('pid1')
        ),
        down=True
    )


def _create_root_dir(tm_env, container_dir, root_dir, app):
    """Prepares chrooted environment and creates all mountpoints.

    :param tm_env:
        Treadmill application environment
    :type tm_env:
        `appenv.AppEnvironment`
    """
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
    fs.chroot_init(root_dir)
    fs.mount_filesystem(localdisk['block_dev'], root_dir)
    fs.make_rootfs(root_dir, app.proid)

    fs.configure_plugins(tm_env.root, root_dir, app)

    # Ensure .etc directory is clean in case of volume restore.
    try:
        shutil.rmtree(os.path.join(root_dir, '.etc'))
    except OSError as err:
        if err.errno != errno.ENOENT:
            raise

    shutil.copytree(
        os.path.join(tm_env.root, 'etc'),
        os.path.join(root_dir, '.etc')
    )

    shutil.copyfile(
        '/etc/hosts',
        os.path.join(root_dir, '.etc/hosts')
    )
    shutil.copyfile(
        '/etc/hosts',
        os.path.join(root_dir, '.etc/hosts.original')
    )

    hosts_aliases = os.path.join(root_dir, '.etc', 'hosts-aliases')
    fs.mkdir_safe(hosts_aliases)

    pwnam = pwd.getpwnam(app.proid)
    os.chown(hosts_aliases, pwnam.pw_uid, pwnam.pw_gid)

    # Always use our own resolv.conf. Safe to rbind, as we are running in
    # private mount subsystem by now.
    subproc.check_call(
        [
            'mount', '-n', '--bind',
            os.path.join(tm_env.root, 'etc/resolv.conf'),
            '/etc/resolv.conf'
        ]
    )


def _share_cgroup_info(app, root_dir):
    """Shares subset of cgroup tree with the container."""
    # Bind /cgroup/memory inside chrooted environment to /cgroup/.../memory
    # of the container.
    unique_name = appcfg.app_unique_name(app)
    cgrp = os.path.join('treadmill', 'apps', unique_name)

    # FIXME(boysson): This should be removed and proper cgroups should be
    #                 exposed (readonly). This is so that tools that
    #                 (correctly) read /proc/self/cgroups can access cgroup
    #                 data.
    shared_subsystems = ['memory']
    for subsystem in shared_subsystems:
        fs.mkdir_safe(os.path.join(root_dir, 'cgroup', subsystem))
        fs.mount_bind(root_dir,
                      os.path.join('/cgroup', subsystem),
                      cgroups.makepath(subsystem, cgrp))


###############################################################################
# Port/socket allocations

def _allocate_sockets(environment, host_ip, sock_type, count):
    """Return a list of `count` socket bound to an ephemeral port.
    """
    # TODO(boysson): this should probably be abstracted away
    if environment == 'prod':
        port_pool = xrange(iptables.PROD_PORT_LOW,
                           iptables.PROD_PORT_HIGH + 1)
    else:
        port_pool = xrange(iptables.NONPROD_PORT_LOW,
                           iptables.NONPROD_PORT_HIGH + 1)

    port_pool = random.sample(port_pool, iptables.PORT_SPAN)

    # socket objects are closed on GC so we need to return
    # them and expect the caller to keep them around while needed
    sockets = []

    for real_port in port_pool:
        if len(sockets) == count:
            break

        socket_ = socket.socket(socket.AF_INET, sock_type)
        socket_.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            socket_.bind((host_ip, real_port))
        except socket.error as err:
            if err.errno == errno.EADDRINUSE:
                continue
            raise

        sockets.append(socket_)
    else:
        raise exc.ContainerSetupError(
            'run.alloc_sockets:{0} < {1}'.format(len(sockets), count))

    return sockets


def _allocate_network_ports_proto(host_ip, manifest, proto, so_type):
    """Allocate ports for named and unnamed endpoints given protocol."""
    ephemeral_count = manifest['ephemeral_ports'].get(proto, 0)
    if isinstance(ephemeral_count, list):
        ephemeral_count = len(ephemeral_count)

    endpoints = [ep for ep in manifest['endpoints']
                 if ep.get('proto', 'tcp') == proto]
    endpoints_count = len(endpoints)

    sockets = _allocate_sockets(
        manifest['environment'],
        host_ip,
        so_type,
        endpoints_count + ephemeral_count
    )

    for idx, endpoint in enumerate(endpoints):
        sock = sockets[idx]
        endpoint['real_port'] = sock.getsockname()[1]

        # Specifying port 0 tells runtime that application wants to
        # have same numeric port value in the container and in
        # the public interface.
        #
        # This is needed for applications that advertise ports they
        # listen on to other members of the app/cluster.
        if endpoint['port'] == 0:
            endpoint['port'] = endpoint['real_port']

    # Ephemeral port are the rest of the ports
    manifest['ephemeral_ports'][proto] = [
        sock.getsockname()[1]
        for sock in sockets[endpoints_count:]
    ]

    return sockets


def _allocate_network_ports(host_ip, manifest):
    """Allocate ports for named and unnamed endpoints.

    :returns:
        ``list`` of bound sockets
    """
    tcp_sockets = _allocate_network_ports_proto(host_ip,
                                                manifest,
                                                'tcp',
                                                socket.SOCK_STREAM)
    udp_sockets = _allocate_network_ports_proto(host_ip,
                                                manifest,
                                                'udp',
                                                socket.SOCK_DGRAM)
    return tcp_sockets + udp_sockets


###############################################################################
#
def _prepare_ldpreload(root_dir, ldpreloads):
    """Add mandatory ldpreloads to the container environment."""
    _LOGGER.info('Configuring /etc/ld.so.preload: %r', ldpreloads)
    if not ldpreloads:
        return

    fs.mkdir_safe(os.path.join(root_dir, '.etc'))
    new_ldpreload = os.path.join(root_dir, '.etc/ld.so.preload')
    try:
        shutil.copyfile('/etc/ld.so.preload', new_ldpreload)
    except IOError as err:
        if err.errno == errno.ENOENT:
            _LOGGER.info('/etc/ld.so.preload not found, creating empty.')
        else:
            # TODO: should we abort?
            _LOGGER.error('copy /etc/ld.so.preload, errno: %s', err.errno)
        with open('/etc/ld.so.preload', 'w') as _:
            pass

    with open(new_ldpreload, 'a') as new_ldpreload_f:
        new_ldpreload_f.write('\n'.join(ldpreloads) + '\n')
