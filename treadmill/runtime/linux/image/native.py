"""A collection of native images.
"""

import errno
import glob
import logging
import os
import pwd
import shutil
import stat

import treadmill

from treadmill import appcfg
from treadmill import cgroups
from treadmill import fs
from treadmill import runtime
from treadmill import subproc
from treadmill import supervisor
from treadmill import utils

from . import fs as image_fs
from . import _image_base
from . import _repository_base


_LOGGER = logging.getLogger(__name__)

_CONTAINER_ENV_DIR = 'environ'


def create_environ_dir(env_dir, app):
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
        'TREADMILL_HOST_IP': app.network.external_ip,
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

    env['TREADMILL_CONTAINER_IP'] = app.network.vip

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


def create_supervision_tree(container_dir, app):
    """Creates s6 supervision tree."""
    # Disable R0915: Too many statements
    # pylint: disable=R0915
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

    app_json = os.path.join(root_dir, 'app.json')

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
            treadmill.TREADMILL_BIN, cell, app_json)
        utils.create_script(
            os.path.join(sys_dir, 'vring.%s' % cell, 'run'),
            'supervisor.run_sys',
            cmd=cmd
        )
        _create_logrun(os.path.join(sys_dir, 'vring.%s' % cell))

    # Create endpoint presence service
    presence_monitor_cmd = '%s sproc presence monitor %s %s' % (
        treadmill.TREADMILL_BIN,
        app_json,
        container_dir
    )
    presence_register_cmd = '%s sproc presence register %s %s' % (
        treadmill.TREADMILL_BIN,
        app_json,
        container_dir
    )
    shadow_etc = os.path.join(container_dir, 'overlay', 'etc')
    host_aliases_cmd = '%s sproc host-aliases --aliases-dir %s %s %s' % (
        treadmill.TREADMILL_BIN,
        os.path.join(shadow_etc, 'host-aliases'),
        os.path.join(shadow_etc, 'hosts.original'),
        os.path.join(shadow_etc, 'hosts'),
    )

    _create_sysrun(sys_dir, 'monitor', presence_monitor_cmd)
    _create_sysrun(sys_dir, 'register', presence_register_cmd)
    _create_sysrun(sys_dir, 'hostaliases', host_aliases_cmd)

    cmd = None
    args = None

    if hasattr(app, 'command'):
        cmd = app.command

    if hasattr(app, 'args'):
        args = app.args

    if not cmd:
        cmd = subproc.resolve('s6_svscan')
        if not args:
            args = ['/services']

    _create_sysrun(
        sys_dir,
        'start_container',
        '%s %s %s -m -p -i %s %s' % (
            subproc.resolve('chroot'),
            root_dir,
            subproc.resolve('pid1'),
            cmd,
            ' '.join(args)
        ),
        down=True
    )


def make_fsroot(root, proid):
    """Initializes directory structure for the container in a new root.

     - Bind directories in parent / (with exceptions - see below.)
     - Skip /tmp, create /tmp in the new root with correct permissions.
     - Selectively create / bind /var.
       - /var/tmp (new)
       - /var/logs (new)
       - /var/spool - create empty with dirs.
     - Bind everything in /var, skipping /spool/tickets
     """
    newroot_norm = fs.norm_safe(root)
    mounts = [
        '/bin',
        '/common',
        '/dev',
        '/etc',
        '/home',
        '/lib',
        '/lib64',
        '/mnt',
        '/proc',
        '/sbin',
        '/srv',
        '/sys',
        '/usr',
        '/var/lib/sss',
        '/var/tmp/treadmill/env',
        '/var/tmp/treadmill/spool',
    ] + glob.glob('/opt/*')

    emptydirs = [
        '/tmp',
        '/opt',
        '/var/empty',
        '/var/run',
        '/var/spool/keytabs',
        '/var/spool/tickets',
        '/var/spool/tokens',
        '/var/tmp',
        '/var/tmp/cores',
    ]

    stickydirs = [
        '/tmp',
        '/opt',
        '/var/spool/keytabs',
        '/var/spool/tickets',
        '/var/spool/tokens',
        '/var/tmp',
        '/var/tmp/cores/',
    ]

    for directory in emptydirs:
        _LOGGER.debug('Creating empty dir: %s', directory)
        fs.mkdir_safe(newroot_norm + directory)

    for directory in stickydirs:
        os.chmod(newroot_norm + directory, 0o777 | stat.S_ISVTX)

    for mount in mounts:
        if os.path.exists(mount):
            fs.mount_bind(newroot_norm, mount)

    # Mount .../tickets .../keytabs on tempfs, so that they will be cleaned
    # up when the container exits.
    #
    # TODO: Do we need to have a single mount for all tmpfs dirs?
    for tmpfsdir in ['/var/spool/tickets', '/var/spool/keytabs',
                     '/var/spool/tokens']:
        fs.mount_tmpfs(newroot_norm, tmpfsdir, '4M')


def etc_overlay(tm_env, container_dir, root_dir, app):
    """Create overlay configuration (etc) files for the container.
    """
    # ldpreloads
    _prepare_ldpreload(container_dir, app)
    # hosts
    _prepare_hosts(container_dir, app)
    # resolv.conf
    _prepare_resolv_conf(tm_env, container_dir)
    # sshd PAM configuration
    _prepare_pam_sshd(tm_env, container_dir, app)
    # bind prepared inside container
    _bind_etc_overlay(container_dir, root_dir)


def _prepare_ldpreload(container_dir, app):
    """Add mandatory ldpreloads to the container environment.
    """
    etc_dir = os.path.join(container_dir, 'overlay', 'etc')
    fs.mkdir_safe(etc_dir)
    new_ldpreload = os.path.join(etc_dir, 'ld.so.preload')

    try:
        shutil.copyfile('/etc/ld.so.preload', new_ldpreload)
    except IOError as err:
        if err.errno != errno.ENOENT:
            raise
        _LOGGER.info('/etc/ld.so.preload not found, creating empty.')
        utils.touch(new_ldpreload)

    ldpreloads = []
    if app.ephemeral_ports.tcp or app.ephemeral_ports.udp:
        treadmill_bind_preload = subproc.resolve('treadmill_bind_preload.so')
        ldpreloads.append(treadmill_bind_preload)

    if not ldpreloads:
        return

    _LOGGER.info('Configuring /etc/ld.so.preload: %r', ldpreloads)
    with open(new_ldpreload, 'a') as f:
        f.write('\n'.join(ldpreloads) + '\n')


def _prepare_hosts(container_dir, app):
    """Create a hosts file for the container.
    """
    etc_dir = os.path.join(container_dir, 'overlay', 'etc')
    fs.mkdir_safe(etc_dir)
    new_hosts = os.path.join(etc_dir, 'hosts')
    new_hosts_orig = os.path.join(etc_dir, 'hosts.original')
    new_host_aliases = os.path.join(etc_dir, 'host-aliases')

    shutil.copyfile(
        '/etc/hosts',
        new_hosts
    )
    shutil.copyfile(
        '/etc/hosts',
        new_hosts_orig
    )
    fs.mkdir_safe(new_host_aliases)

    pwnam = pwd.getpwnam(app.proid)
    os.chown(new_host_aliases, pwnam.pw_uid, pwnam.pw_gid)


def _prepare_pam_sshd(tm_env, container_dir, app):
    """Override pam.d sshd stack with special sshd pam stack.
    """
    pamd_dir = os.path.join(container_dir, 'overlay', 'etc', 'pam.d')
    fs.mkdir_safe(pamd_dir)
    new_pam_sshd = os.path.join(pamd_dir, 'sshd')

    if app.shared_network:
        template_pam_sshd = os.path.join(
            tm_env.root, 'etc', 'pam.d', 'sshd.shared_network')
    else:
        template_pam_sshd = os.path.join(
            tm_env.root, 'etc', 'pam.d', 'sshd')

    if not os.path.exists(template_pam_sshd):
        template_pam_sshd = '/etc/pam.d/sshd'

    shutil.copyfile(
        template_pam_sshd,
        new_pam_sshd
    )


def _prepare_resolv_conf(tm_env, container_dir):
    """Create an resolv.conf file for the container.
    """
    etc_dir = os.path.join(container_dir, 'overlay', 'etc')
    fs.mkdir_safe(etc_dir)
    new_resolv_conf = os.path.join(etc_dir, 'resolv.conf')

    # TODO(boysson): This should probably be based instead on /etc/resolv.conf
    #                for other resolver options
    template_resolv_conf = os.path.join(tm_env.root, 'etc', 'resolv.conf')
    if not os.path.exists(template_resolv_conf):
        template_resolv_conf = '/etc/resolv.conf'

    shutil.copyfile(
        template_resolv_conf,
        new_resolv_conf
    )


def _bind_etc_overlay(container_dir, root_dir):
    """Create the overlay in the container."""
    # Overlay overrides container configs
    #   - /etc/resolv.conf, so that container always uses dnscache.
    #   - pam.d sshd stack with special sshd pam that unshares network.
    #   - /etc/ld.so.preload to enforce necessary system hooks
    #
    overlay_dir = os.path.join(container_dir, 'overlay')
    for overlay_file in ['etc/hosts',
                         'etc/host-aliases',
                         'etc/ld.so.preload',
                         'etc/pam.d/sshd',
                         'etc/resolv.conf']:
        fs.mount_bind(root_dir, os.path.join('/', overlay_file),
                      target=os.path.join(overlay_dir, overlay_file),
                      bind_opt='--bind')

    # Also override resolv.conf in the current mount namespace so that
    # system services have access to out resolver.
    fs.mount_bind('/', '/etc/resolv.conf',
                  target=os.path.join(overlay_dir, 'etc/resolv.conf'),
                  bind_opt='--bind')


def share_cgroup_info(app, root_dir):
    """Shares subset of cgroup tree with the container."""
    # Bind /cgroup/memory inside chrooted environment to /cgroup/.../memory
    # of the container.
    unique_name = appcfg.app_unique_name(app)
    cgrp = os.path.join('treadmill', 'apps', unique_name)

    # FIXME: This should be removed and proper cgroups should be
    #        exposed (readonly). This is so that tools that
    #        (correctly) read /proc/self/cgroups can access cgroup
    #        data.
    shared_subsystems = ['memory']
    for subsystem in shared_subsystems:
        fs.mkdir_safe(os.path.join(root_dir, 'cgroup', subsystem))
        fs.mount_bind(root_dir,
                      os.path.join('/cgroup', subsystem),
                      cgroups.makepath(subsystem, cgrp))


class NativeImage(_image_base.Image):
    """Represents a native image."""
    __slots__ = (
        'tm_env'
    )

    def __init__(self, tm_env):
        self.tm_env = tm_env

    def unpack(self, container_dir, root_dir, app):
        make_fsroot(root_dir, app.proid)

        image_fs.configure_plugins(self.tm_env, root_dir, app)

        # FIXME: Lots of things are still reading this file.
        #        Copy updated state manifest as app.json in the
        #        container_dir so it is visible in chrooted env.
        shutil.copy(os.path.join(container_dir, runtime.STATE_JSON),
                    os.path.join(root_dir, appcfg.APP_JSON))

        # FIXME: env_dir should be in a well defined location (part of the
        #        container "API").
        env_dir = os.path.join(root_dir, 'environ')
        create_environ_dir(env_dir, app)
        create_supervision_tree(container_dir, app)

        share_cgroup_info(app, root_dir)
        etc_overlay(self.tm_env, container_dir, root_dir, app)


class NativeImageRepository(_repository_base.ImageRepository):
    """A collection of native images."""

    def __init__(self, tm_env):
        super(NativeImageRepository, self).__init__(tm_env)

    def get(self, url):
        return NativeImage(self.tm_env)
