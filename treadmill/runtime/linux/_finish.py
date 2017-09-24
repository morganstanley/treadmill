"""Provides functions that are used when apps are finished.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import glob
import io
import json
import logging
import os
import shutil
import signal
import socket
import tarfile

import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

from treadmill import appevents
from treadmill import appcfg
from treadmill import apphook
from treadmill import firewall
from treadmill import fs
from treadmill import iptables
from treadmill import logcontext as lc
from treadmill import runtime
from treadmill import rrdutils
from treadmill import services
from treadmill import supervisor
from treadmill import sysinfo
from treadmill import utils

from treadmill.appcfg import abort as app_abort
from treadmill.apptrace import events


_LOGGER = logging.getLogger(__name__)

_ARCHIVE_LIMIT = utils.size_to_bytes('1G')


def finish(tm_env, container_dir):
    """Frees allocated resources and mark then as available.
    """
    with lc.LogContext(_LOGGER, os.path.basename(container_dir),
                       lc.ContainerAdapter):
        _LOGGER.info('finishing %r', container_dir)

        _stop_container(container_dir)
        data_dir = os.path.join(container_dir, 'data')

        app = runtime.load_app(data_dir)
        if app is not None:
            _cleanup(tm_env, data_dir, app)
        else:
            app = runtime.load_app(data_dir, appcfg.APP_JSON)

        if app is not None:
            # Check if application reached restart limit inside the container.
            #
            # The container directory will be moved, this check is done first.
            #
            # If restart limit was reached, application node will be removed
            # from Zookeeper at the end of the cleanup process, indicating to
            # the scheduler that the server is ready to accept new load.
            exitinfo, aborted, oom = _collect_exit_info(data_dir)

            # All resources are cleaned up. If the app terminated inside the
            # container, remove the node from Zookeeper, which will notify the
            # scheduler that it is safe to reuse the host for other load.
            if aborted is not None:
                app_abort.report_aborted(tm_env, app.name,
                                         why=aborted.get('why'),
                                         payload=aborted.get('payload'))

            elif oom:
                _post_oom_event(tm_env, app)

            elif exitinfo is not None:
                _post_exit_event(tm_env, app, exitinfo)

            else:
                # No need to post event as evicted notification is handled by
                # master.
                _LOGGER.info('Evicted: %s', app.name)

        # cleanup monitor with container information
        if app:
            apphook.cleanup(tm_env, app, container_dir)


def _collect_exit_info(container_dir):
    """Read exitinfo, check if app was aborted and why.

    :returns ``(exitinfo, aborted)``:
        Returns a tuple of exitinfo, a ``(service_name,return_code,signal)`` if
        present or None otherwise, and aborted reason is persent or None
        otherwise.
    """
    exitinfo = aborted = None

    exitinfo_file = os.path.join(container_dir, 'exitinfo')
    try:
        with io.open(exitinfo_file) as f:
            exitinfo = json.load(f)

    except IOError:
        _LOGGER.debug('exitinfo file does not exist: %r', exitinfo_file)

    aborted_file = os.path.join(container_dir, 'aborted')
    try:
        with io.open(aborted_file) as f:
            try:
                aborted = json.load(f)
            except ValueError:
                _LOGGER.warn('Invalid json in aborted file: %s', aborted_file)
                aborted = app_abort.ABORTED_UNKNOWN

    except IOError:
        _LOGGER.debug('aborted file does not exist: %r', aborted_file)

    oom_file = os.path.join(container_dir, 'oom')
    oom = os.path.exists(oom_file)
    if not oom:
        _LOGGER.debug('oom file does not exist: %r', oom_file)

    return exitinfo, aborted, oom


def _stop_container(container_dir):
    """Stop container, remove from supervision tree."""
    try:
        supervisor.control_service(container_dir,
                                   supervisor.ServiceControlAction.down,
                                   wait=supervisor.ServiceWaitAction.down)

    except subprocess.CalledProcessError as err:
        # The directory was already removed as the app was killed by the user.
        #
        # There is nothing to be done here, just log and exit.
        if err.returncode in (supervisor.ERR_COMMAND, supervisor.ERR_NO_SUP):
            _LOGGER.info('Cannot control supervisor of %r.',
                         container_dir)
        else:
            raise


def _post_oom_event(tm_env, app):
    """Post oom as killed container."""
    appevents.post(
        tm_env.app_events_dir,
        events.KilledTraceEvent(
            instanceid=app.name,
            is_oom=True,
        )
    )


def _post_exit_event(tm_env, app, exitinfo):
    """Post exit event based on exit reason."""
    appevents.post(
        tm_env.app_events_dir,
        events.FinishedTraceEvent(
            instanceid=app.name,
            rc=exitinfo.get('return_code', 256),
            signal=exitinfo.get('signal', 256),
            payload=exitinfo
        )
    )


def _cleanup(tm_env, container_dir, app):
    """Cleanup a container that actually ran.
    """
    # Too many branches.
    #
    # pylint: disable=R0912

    rootdir = os.path.join(container_dir, 'root')
    # Generate a unique name for the app
    unique_name = appcfg.app_unique_name(app)
    # Create service clients
    cgroup_client = tm_env.svc_cgroup.make_client(
        os.path.join(container_dir, 'resources', 'cgroups')
    )
    localdisk_client = tm_env.svc_localdisk.make_client(
        os.path.join(container_dir, 'resources', 'localdisk')
    )
    network_client = tm_env.svc_network.make_client(
        os.path.join(container_dir, 'resources', 'network')
    )

    # Make sure all processes are killed
    # FIXME(boysson): Should we use `kill_apps_in_cgroup` instead?
    _kill_apps_by_root(rootdir)

    # Setup the archive filename that will hold this container's data
    filetime = utils.datetime_utcnow().strftime('%Y%m%d_%H%M%S%f')
    archive_filename = os.path.join(
        container_dir,
        '{instance_name}_{hostname}_{timestamp}.tar'.format(
            instance_name=appcfg.appname_task_id(app.name),
            hostname=sysinfo.hostname(),
            timestamp=filetime
        )
    )

    # Tar up container root filesystem if archive list is in manifest
    try:
        localdisk = localdisk_client.get(unique_name)
        fs.archive_filesystem(
            localdisk['block_dev'],
            rootdir,
            archive_filename,
            app.archive
        )
    except services.ResourceServiceError:
        _LOGGER.warning('localdisk never allocated')
    except subprocess.CalledProcessError:
        _LOGGER.exception('Unable to archive root device of %r',
                          unique_name)
    except:  # pylint: disable=W0702
        _LOGGER.exception('Unknown exception while archiving %r',
                          unique_name)

    # Destroy the volume
    try:
        localdisk_client.delete(unique_name)
    except (IOError, OSError) as err:
        if err.errno == errno.ENOENT:
            pass
        else:
            raise

    if not app.shared_network:
        _cleanup_network(tm_env, app, network_client)

    # Add metrics to archive
    rrd_file = os.path.join(
        tm_env.metrics_dir,
        'apps',
        '{name}-{instanceid}-{uniqueid}.rrd'.format(
            name=app.app,
            instanceid=app.task,
            uniqueid=app.uniqueid,
        )
    )
    rrdutils.flush_noexc(rrd_file)
    _copy_metrics(rrd_file, container_dir)

    # Cleanup our cgroup resources
    try:
        cgroup_client.delete(unique_name)
    except (IOError, OSError) as err:
        if err.errno == errno.ENOENT:
            pass
        else:
            raise

    try:
        _archive_logs(tm_env, appcfg.app_unique_name(app), container_dir)
    except Exception:  # pylint: disable=W0703
        _LOGGER.exception('Unexpected exception storing local logs.')


def _cleanup_network(tm_env, app, network_client):
    """Cleanup the network part of a container.
    """
    # Generate a unique name for the app
    unique_name = appcfg.app_unique_name(app)

    try:
        app_network = network_client.get(unique_name)

    except services.ResourceServiceError:
        _LOGGER.warning('network never allocated')
        return

    if app_network is None:
        _LOGGER.info('Network resource already freed')
        return

    # Unconfigure passthrough
    if hasattr(app, 'passthrough'):
        _LOGGER.info('Deleting passthrough for: %r',
                     app.passthrough)
        # Resolve all the hosts
        # FIXME: There is no guarantie the hosts will resolve to
        #        the same IPs as they did during creation.
        ips = set([socket.gethostbyname(host)
                   for host in app.passthrough])
        for ip in ips:
            tm_env.rules.unlink_rule(
                chain=iptables.PREROUTING_PASSTHROUGH,
                rule=firewall.PassThroughRule(src_ip=ip,
                                              dst_ip=app_network['vip']),
                owner=unique_name,
            )

    if app.vring:
        # Mark the container's IP as VRing enabled
        _LOGGER.debug('removing %r from VRing set', app_network['vip'])
        iptables.rm_ip_set(
            iptables.SET_VRING_CONTAINERS,
            app_network['vip']
        )

    for endpoint in app.endpoints:
        tm_env.rules.unlink_rule(
            chain=iptables.PREROUTING_DNAT,
            rule=firewall.DNATRule(proto=endpoint.proto,
                                   dst_ip=app_network['external_ip'],
                                   dst_port=endpoint.real_port,
                                   new_ip=app_network['vip'],
                                   new_port=endpoint.port),
            owner=unique_name,
        )
        tm_env.rules.unlink_rule(
            chain=iptables.POSTROUTING_SNAT,
            rule=firewall.SNATRule(proto=endpoint.proto,
                                   src_ip=app_network['vip'],
                                   src_port=endpoint.port,
                                   new_ip=app_network['external_ip'],
                                   new_port=endpoint.real_port),
            owner=unique_name,
        )
        # See if this was an "infra" endpoint and if so remove it
        # from the whitelist set.
        if getattr(endpoint, 'type', None) == 'infra':
            _LOGGER.debug('removing %s:%s from infra services set',
                          app_network['vip'], endpoint.port)
            iptables.rm_ip_set(
                iptables.SET_INFRA_SVC,
                '{ip},{proto}:{port}'.format(
                    ip=app_network['vip'],
                    proto=endpoint.proto,
                    port=endpoint.port,
                )
            )

    _cleanup_ephemeral_ports(
        tm_env,
        unique_name,
        app_network['external_ip'],
        app_network['vip'],
        app.ephemeral_ports.tcp,
        'tcp'
    )
    _cleanup_ephemeral_ports(
        tm_env,
        unique_name,
        app_network['external_ip'],
        app_network['vip'],
        app.ephemeral_ports.udp,
        'udp'
    )

    # Terminate any entries in the conntrack table
    iptables.flush_conntrack_table(app_network['vip'])
    # Cleanup network resources
    network_client.delete(unique_name)


def _cleanup_ephemeral_ports(tm_env, unique_name,
                             external_ip, vip, ports, proto):
    """Cleanup firewall rules for ports."""
    for port in ports:
        # We treat ephemeral ports as infra, consistent with current
        # prodperim behavior.
        iptables.rm_ip_set(
            iptables.SET_INFRA_SVC,
            '{ip},{proto}:{port}'.format(ip=vip,
                                         proto=proto,
                                         port=port)
        )
        dnatrule = firewall.DNATRule(proto=proto,
                                     dst_ip=external_ip,
                                     dst_port=port,
                                     new_ip=vip,
                                     new_port=port)
        tm_env.rules.unlink_rule(
            chain=iptables.PREROUTING_DNAT,
            rule=dnatrule,
            owner=unique_name
        )


def _kill_apps_by_root(approot):
    """Kills all processes that run in a given chroot."""
    norm_approot = os.path.normpath(approot)
    procs = glob.glob('/proc/[0-9]*')
    procs_killed = 0
    for proc in procs:
        pid = proc.split('/')[2]
        try:
            procroot = os.readlink(proc + '/root')
            if os.path.normpath(procroot) == norm_approot:
                _LOGGER.info('kill %s, root: %s', proc, procroot)
                os.kill(int(pid), signal.SIGKILL)
                procs_killed += 1
        # pylint: disable=W0702
        except:
            _LOGGER.critical('Cannot open %s/root', proc, exc_info=True)

    return procs_killed


def _copy_metrics(metrics_file, container_dir):
    """Safe copy metrics file to container directory."""
    _LOGGER.info('Copy metrics: %s to %s', metrics_file, container_dir)
    try:
        # TODO: We should factor out rrd specificities to a module
        shutil.copy(metrics_file, os.path.join(container_dir, 'metrics.rrd'))

    except IOError as err:
        if err.errno == errno.ENOENT:
            _LOGGER.info('metrics file not found: %s.', metrics_file)
        else:
            raise


def _cleanup_archive_dir(tm_env):
    """Delete old files from archive directory if space exceeds the threshold.
    """
    archives = glob.glob(os.path.join(tm_env.archives_dir, '*'))
    infos = []
    dir_size = 0
    for archive in archives:
        stat = os.stat(archive)
        dir_size += stat.st_size
        infos.append((stat.st_mtime, stat.st_size, archive))

    if dir_size <= _ARCHIVE_LIMIT:
        _LOGGER.info('Archive directory below threshold: %s', dir_size)
        return

    _LOGGER.info('Archive directory above threshold: %s gt %s',
                 dir_size, _ARCHIVE_LIMIT)
    infos.sort()
    while dir_size > _ARCHIVE_LIMIT:
        ctime, size, archive = infos.pop(0)
        dir_size -= size
        _LOGGER.info('Unlink old archive %s: ctime: %s, size: %s',
                     archive, ctime, size)
        fs.rm_safe(archive)


def _archive_logs(tm_env, name, container_dir):
    """Archive latest sys and services logs."""
    _cleanup_archive_dir(tm_env)

    sys_archive_name = os.path.join(tm_env.archives_dir, name + '.sys.tar.gz')
    app_archive_name = os.path.join(tm_env.archives_dir, name + '.app.tar.gz')

    def _add(archive, filename):
        """Safely add file to archive."""
        try:
            archive.add(filename, filename[len(container_dir) + 1:])
        except OSError as err:
            if err.errno == errno.ENOENT:
                _LOGGER.warning('File not found: %s', filename)
            else:
                raise

    with tarfile.open(sys_archive_name, 'w:gz') as f:
        logs = glob.glob(
            os.path.join(container_dir, 'sys', '*', 'data', 'log', 'current'))
        for log in logs:
            _add(f, log)

        metrics = glob.glob(os.path.join(container_dir, '*.rrd'))
        for metric in metrics:
            _add(f, metric)

        yml_cfgs = glob.glob(os.path.join(container_dir, '*.yml'))
        json_cfgs = glob.glob(os.path.join(container_dir, '*.json'))
        for cfg in yml_cfgs + json_cfgs:
            _add(f, cfg)

        _add(f, os.path.join(container_dir, 'log', 'current'))

    with tarfile.open(app_archive_name, 'w:gz') as f:
        logs = glob.glob(
            os.path.join(container_dir, 'services', '*', 'data', 'log',
                         'current'))
        for log in logs:
            _add(f, log)
