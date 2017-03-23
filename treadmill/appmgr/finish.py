"""Provides functions that are used when apps are finished."""


import errno
import glob
import importlib
import logging
import os
import shutil
import signal
import socket
import subprocess
import tarfile

import yaml
import kazoo

from treadmill import appevents
from treadmill import appmgr
from treadmill import firewall
from treadmill import fs
from treadmill import iptables
from treadmill import logcontext as lc
from treadmill import rrdutils
from treadmill import services
from treadmill import subproc
from treadmill import supervisor
from treadmill import sysinfo
from treadmill import utils
from treadmill import zknamespace as z
from treadmill import zkutils

from treadmill.apptrace import events

from . import manifest as app_manifest


_LOGGER = lc.ContainerAdapter(logging.getLogger(__name__))

_APP_YML = 'app.yml'
_STATE_YML = 'state.yml'
_ARCHIVE_LIMIT = utils.size_to_bytes('1G')


def finish(tm_env, zkclient, container_dir):
    """Frees allocated resources and mark then as available.

    :param tm_env:
        Treadmill application environment
    :type tm_env:
        `appmgr.AppEnvironment`
    :param container_dir:
        Full path to the application container directory
    :type container_dir:
        ``str``
    """

    # FIXME(boysson): Clean should be done inside the container. The watchdog
    #                 value below is inflated to account for the extra
    #                 archiving time.
    name_dir = os.path.basename(container_dir)
    with lc.LogContext(_LOGGER, name_dir, lc.ContainerAdapter) as log:
        log.logger.info('finishing %r', container_dir)
        watchdog_name = '{name}-{app}'.format(name=__name__,
                                              app=name_dir)
        watchdog = tm_env.watchdogs.create(watchdog_name, '5m', 'Cleanup of '
                                           '%r stalled' % container_dir)

        _stop_container(container_dir)

        # Check if application reached restart limit inside the container.
        #
        # The container directory will be moved, this check is done first.
        #
        # If restart limit was reached, application node will be removed from
        # Zookeeper at the end of the cleanup process, indicating to the
        # scheduler that the server is ready to accept new load.
        exitinfo, aborted, aborted_reason = _collect_exit_info(container_dir)

        app = _load_app(container_dir, _STATE_YML)
        if app:
            _cleanup(tm_env, zkclient, container_dir, app)
        else:
            app = _load_app(container_dir, _APP_YML)

        if app:
            # All resources are cleaned up. If the app terminated inside the
            # container, remove the node from Zookeeper, which will notify the
            # scheduler that it is safe to reuse the host for other load.
            if aborted:
                appevents.post(
                    tm_env.app_events_dir,
                    events.AbortedTraceEvent(
                        instanceid=app.name,
                        why=None,  # TODO(boysson): extract this info
                        payload=aborted_reason
                    )
                )

            if exitinfo:
                _post_exit_event(tm_env, app, exitinfo)

        # Delete the app directory (this includes the tarball, if any)
        shutil.rmtree(container_dir)

        # cleanup was succesful, remove the watchdog
        watchdog.remove()
        log.logger.info('Finished cleanup: %s', container_dir)


def _collect_exit_info(container_dir):
    """Read exitinfo, check if app was aborted and why."""
    exitinfo_file = os.path.join(container_dir, 'exitinfo')
    exitinfo = _read_exitinfo(exitinfo_file)
    _LOGGER.info('check for exitinfo file %r: %r', exitinfo_file, exitinfo)

    aborted_file = os.path.join(container_dir, 'aborted')
    aborted = os.path.exists(aborted_file)
    _LOGGER.info('check for aborted file: %s, %s', aborted_file, aborted)

    aborted_reason = None
    if aborted:
        with open(aborted_file) as f:
            aborted_reason = f.read()

    return exitinfo, aborted, aborted_reason


def _load_app(container_dir, app_yml):
    """Load app from original manifest, pre-configured."""
    manifest_file = os.path.join(container_dir, app_yml)

    try:
        manifest = app_manifest.read(manifest_file)
        _LOGGER.debug('Manifest: %r', manifest)
        return utils.to_obj(manifest)

    except IOError as err:
        if err.errno != errno.ENOENT:
            raise

        _LOGGER.critical('Manifest file does not exit: %r', manifest_file)
        return None


def _stop_container(container_dir):
    """Stop container, remove from supervision tree."""
    try:
        subproc.check_call(['s6-svc', '-d', container_dir])
        subproc.check_call(['s6-svwait', '-d', container_dir])

    except subprocess.CalledProcessError as err:
        # The directory was already removed as the app was killed by the user.
        #
        # There is nothing to be done here, just log and exit.
        if err.returncode in (supervisor.ERR_COMMAND, supervisor.ERR_NO_SUP):
            _LOGGER.info('Cannot control supervisor of %r.',
                         container_dir)
        else:
            raise


def _post_exit_event(tm_env, app, exitinfo):
    """Post exit event based on exit reason."""
    if exitinfo.get('killed'):
        event = events.KilledTraceEvent(
            instanceid=app.name,
            is_oom=bool(exitinfo.get('oom')),
        )
    else:
        event = events.FinishedTraceEvent(
            instanceid=app.name,
            rc=exitinfo.get('rc', 256),
            signal=exitinfo.get('sig', 256),
            payload=exitinfo
        )

    appevents.post(tm_env.app_events_dir, event)


def _cleanup(tm_env, zkclient, container_dir, app):
    """Cleanup a container that actually ran.
    """
    # Too many branches.
    #
    # pylint: disable=R0912

    rootdir = os.path.join(container_dir, 'root')
    # Generate a unique name for the app
    unique_name = appmgr.app_unique_name(app)
    # Create service clients
    cgroup_client = tm_env.svc_cgroup.make_client(
        os.path.join(container_dir, 'cgroups')
    )
    localdisk_client = tm_env.svc_localdisk.make_client(
        os.path.join(container_dir, 'localdisk')
    )
    network_client = tm_env.svc_network.make_client(
        os.path.join(container_dir, 'network')
    )

    # Make sure all processes are killed
    # FIXME(boysson): Should we use `kill_apps_in_cgroup` instead?
    _kill_apps_by_root(rootdir)

    # Setup the archive filename that will hold this container's data
    filetime = utils.datetime_utcnow().strftime('%Y%m%d_%H%M%S%f')
    archive_filename = os.path.join(
        container_dir,
        '{instance_name}_{hostname}_{timestamp}.tar'.format(
            instance_name=appmgr.appname_task_id(app.name),
            hostname=sysinfo.hostname(),
            timestamp=filetime
        )
    )

    # Tar up container root filesystem if archive list is in manifest
    if getattr(app, 'archive', []):
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
            _LOGGER.exception('Unknow exception while archiving %r',
                              unique_name)

    # Destroy the volume
    try:
        localdisk = localdisk_client.delete(unique_name)
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
        _archive_logs(tm_env, container_dir)
    except Exception:  # pylint: disable=W0703
        _LOGGER.exception('Unexpected exception storing local logs.')

    # Append or create the tarball with folders outside of container
    # Compress and send the tarball to HCP
    try:
        archive_filename = fs.tar(sources=container_dir,
                                  target=archive_filename,
                                  compression='gzip').name
        _send_container_archive(zkclient, app, archive_filename)
    except:  # pylint: disable=W0702
        _LOGGER.exception("Failed to update archive")


def _cleanup_network(tm_env, app, network_client):
    """Cleanup the network part of a container.
    """
    # Generate a unique name for the app
    unique_name = appmgr.app_unique_name(app)

    try:
        app_network = network_client.get(unique_name)

    except services.ResourceServiceError:
        _LOGGER.warning('network never allocated')
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
                rule=firewall.PassThroughRule(src_ip=ip,
                                              dst_ip=app_network['vip']),
                owner=unique_name,
            )

    for endpoint in app.endpoints:
        tm_env.rules.unlink_rule(
            rule=firewall.DNATRule(proto=endpoint.proto,
                                   orig_ip=app.host_ip,
                                   orig_port=endpoint.real_port,
                                   new_ip=app_network['vip'],
                                   new_port=endpoint.port),
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

    if hasattr(app, 'ephemeral_ports'):
        for port in app.ephemeral_ports:
            # We treat ephemeral ports as infra, consistent with current
            # prodperim behavior.
            iptables.rm_ip_set(
                iptables.SET_INFRA_SVC,
                '{ip},tcp:{port}'.format(ip=app_network['vip'],
                                         port=port)
            )
            dnatrule = firewall.DNATRule(proto='tcp',
                                         orig_ip=tm_env.host_ip,
                                         orig_port=port,
                                         new_ip=app_network['vip'],
                                         new_port=port)
            tm_env.rules.unlink_rule(rule=dnatrule,
                                     owner=unique_name)

    # Terminate any entries in the conntrack table
    iptables.flush_conntrack_table(app_network['vip'])
    # Cleanup network resources
    network_client.delete(unique_name)


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


def _send_container_archive(zkclient, app, archive_file):
    """This sends the archives of the container to warm storage.

    It sends the archive (tarball) up to WARM storage if the archive is
    configured for the cell.  If it is not configured or it fails for any
    reason, it continues without exception.  This ensures that failures do not
    cause disk to fill up."""

    try:
        # Connect to zk to get the WARM name and auth key
        config = zkutils.with_retry(zkutils.get, zkclient, z.ARCHIVE_CONFIG)

        plugin = importlib.import_module(
            'treadmill.plugins.archive'
        )
        # yes, we want to call with **
        uploader = plugin.Uploader(**config)
        uploader(archive_file, app)
    except kazoo.client.NoNodeError:
        _LOGGER.error('Archive not configured in zookeeper.')


def _read_exitinfo(exitinfo_file):
    """Read the container finished file.

    Returns:
        `tuple` of (service_name,return_code,signal) if present, None
        otherwise.
    """
    exitinfo = None
    try:
        with open(exitinfo_file) as f:
            exitinfo = yaml.load(f.read())

    except IOError as _err:
        _LOGGER.debug('Unable to read container exitinfo: %s', exitinfo_file)

    return exitinfo


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


def _archive_logs(tm_env, container_dir):
    """Archive latest sys and services logs."""
    _cleanup_archive_dir(tm_env)

    name = os.path.basename(container_dir)
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
            os.path.join(container_dir, 'sys', '*', 'log', 'current'))
        for log in logs:
            _add(f, log)

        metrics = glob.glob(os.path.join(container_dir, '*.rrd'))
        for metric in metrics:
            _add(f, metric)

        cfgs = glob.glob(os.path.join(container_dir, '*.yml'))
        for cfg in cfgs:
            _add(f, cfg)

        _add(f, os.path.join(container_dir, 'run.out'))

    with tarfile.open(app_archive_name, 'w:gz') as f:
        logs = glob.glob(
            os.path.join(container_dir, 'services', '*', 'log', 'current'))
        for log in logs:
            _add(f, log)
