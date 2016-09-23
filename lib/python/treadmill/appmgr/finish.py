"""Provides functions that are used when apps are finished."""

from __future__ import absolute_import

import errno
import glob
import importlib
import logging
import os
import shutil
import signal
import socket
import subprocess

import yaml
import kazoo

from .. import appevents
from .. import appmgr
from .. import firewall
from .. import fs
from .. import iptables
from .. import services
from .. import subproc
from .. import supervisor
from .. import sysinfo
from .. import utils
from .. import zkutils
from .. import rrdutils
from .. import zknamespace as z

from . import manifest as app_manifest


_LOGGER = logging.getLogger(__name__)

_APP_YML = 'app.yml'
_STATE_YML = 'state.yml'


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
    # R0915: Need to refactor long function into smaller pieces.
    # R0912: Too many branches
    #
    # pylint: disable=R0915,R0912
    _LOGGER.info('finishing %r', container_dir)

    # FIXME(boysson): Clean should be done inside the container. The watchdog
    #                 value below is inflated to account for the extra
    #                 archiving time.
    name_dir = os.path.basename(container_dir)
    watchdog_name = '{name}:{app}'.format(name=__name__,
                                          app=name_dir)
    watchdog = tm_env.watchdogs.create(watchdog_name, '5m',
                                       'Cleanup of %r stalled' % container_dir)

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

    app = None
    has_state = False

    try:
        state_file = os.path.join(container_dir, _STATE_YML)
        state = app_manifest.read(state_file)
        _LOGGER.debug('State: %r', state)
        app = utils.to_obj(state)
        has_state = True

    except IOError as err:
        if err.errno == errno.ENOENT:
            _LOGGER.warn('State file does not exit: %r', state_file)
        else:
            raise

    if app is None:
        try:
            manifest_file = os.path.join(container_dir, _APP_YML)
            manifest = app_manifest.read(manifest_file)
            _LOGGER.debug('Manifest: %r', manifest)
            app = utils.to_obj(manifest)

        except IOError as err:
            if err.errno == errno.ENOENT:
                _LOGGER.critical('Manifest file does not exit: %r',
                                 manifest_file)
                watchdog.remove()
                shutil.rmtree(container_dir)
                return
            else:
                raise

    # Check if application reached restart limit inside the container.
    #
    # The container directory will be moved, this check is done first.
    #
    # If restart limit was reached, application node will be removed from
    # Zookeeper at the end of the cleanup process, indicating to the
    # scheduler that the server is ready to accept new load.
    #
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

    if has_state:
        _cleanup(tm_env, zkclient, container_dir, app)

    # Delete the app directory (this includes the tarball, if any)
    shutil.rmtree(container_dir)

    # cleanup was succesful, remove the watchdog
    watchdog.remove()

    # All resources are cleaned up. If the app terminated inside the
    # container, remove the node from Zookeeper, which will notify the
    # scheduler that it is safe to reuse the host for other load.
    eventmsg = None
    if aborted:
        appevents.post(tm_env.app_events_dir, app.name, 'aborted', eventmsg,
                       aborted_reason)

    if exitinfo:
        if exitinfo.get('killed'):
            event = 'killed'
            if exitinfo.get('oom'):
                eventmsg = 'oom'
        else:
            rc = exitinfo.get('rc', 256)
            sig = exitinfo.get('sig', 256)
            event = 'finished'
            eventmsg = '%s.%s' % (rc, sig)

        appevents.post(tm_env.app_events_dir,
                       app.name, event, eventmsg, exitinfo)

    _LOGGER.info('Finished cleanup: %s', app.name)


def _cleanup(tm_env, zkclient, container_dir, app):
    """Cleanup a container that actually ran.
    """
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
            rule=firewall.DNATRule(orig_ip=app.host_ip,
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
                '{ip},tcp:{port}'.format(ip=app_network['vip'],
                                         port=endpoint.port)
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
            dnatrule = firewall.DNATRule(orig_ip=tm_env.host_ip,
                                         orig_port=port,
                                         new_ip=app_network['vip'],
                                         new_port=port)
            tm_env.rules.unlink_rule(rule=dnatrule,
                                     owner=unique_name)

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
