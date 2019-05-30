"""Treadmill container initialization.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import pprint

import click

from treadmill import subproc
from treadmill.fs import linux as fs_linux
from treadmill import cgroups
from treadmill import pivot_root
from treadmill import trace

from treadmill.appcfg import abort as app_abort
from treadmill.appcfg import manifest as app_manifest
from treadmill.trace.app import events as traceevents

_LOGGER = logging.getLogger(__name__)


_EXCLUDE_SUBSYSTEM = 'net_prio'


def get_subsystems():
    """subsystem to join
    we exclude net_prio for now
    as RH6 has issue to create subsubsytem in net_prio
    """
    subsystems = cgroups.mounted_subsystems()

    if _EXCLUDE_SUBSYSTEM in subsystems:
        del subsystems[_EXCLUDE_SUBSYSTEM]

    return subsystems


def _abort(event, container_root):
    """we need to consider two cases
    pivot_root success but mount failure afterwars
    pivot_root fails directly
    """
    if trace.post_ipc('/run/tm_ctl/appevents', event) == 0:
        _LOGGER.warning(
            'Failed to post abort event to socket in new root, trying old path'
        )
        old_uds = os.path.join(container_root, 'run/tm_ctl/appevents')
        trace.post_ipc(old_uds, event)


def _get_remount_cgroup(container_root, cgroup, root_cgroup):
    """get remount cgroup fs to container_root
    """
    # XXX: only support cgroup name as abs path
    assert os.path.isabs(cgroup)
    group = os.path.join(root_cgroup, cgroup.lstrip('/'))
    _LOGGER.info('Current cgroup: %s', group)

    subsystem_mounts = get_subsystems()
    remount = set()
    for (subsystem, mounts) in subsystem_mounts.items():
        mount = mounts[0]
        target_path = os.path.join(mount, group)
        app_subsystem_path = os.path.join(container_root, mount.lstrip('/'))

        _LOGGER.info('To remount cgroups %s => %s',
                     target_path, app_subsystem_path)
        remount.add((target_path, app_subsystem_path))

    return remount


def remount_cgroup(container_root, cgroup, root_cgroup):
    """remount cgroups path to put service cgroup as container root cgroup
    """
    _LOGGER.info('Remounting cgroup paths')
    remount = _get_remount_cgroup(container_root, cgroup, root_cgroup)
    for (target_path, app_subsystem_path) in remount:
        # unmount & mount from /sys/fs/cgroups/<subsystem>/<group> to root dir
        fs_linux.umount_filesystem(app_subsystem_path)
        # dockerd needs to write cgroup path
        fs_linux.mount_bind('/', app_subsystem_path, target_path,
                            read_only=False)


def init():
    """Top level command handler."""
    @click.command(name='start-container')
    @click.option('--container-root', type=click.Path(exists=True),
                  required=True)
    @click.argument('manifest', type=click.Path(exists=True))
    @click.pass_context
    def start_container(ctx, container_root, manifest):
        """Treadmill container boot process.
        """
        _LOGGER.info('Initializing container: %s', container_root)
        app = app_manifest.read(manifest)

        cgroup = ctx.obj.get('CGROUP')
        try:
            # if cgroups set, we need to remount cgroup path
            # so that from cgroup directory we only see container pids
            # <container_root>/sys/fs/cgroup/memory =>
            #   /sys/fs/cgroup/memory/treadmill/apps/<app-inst-unique>/services
            if cgroup:
                remount_cgroup(container_root, cgroup, ctx.obj['ROOT_CGROUP'])

            pivot_root.make_root(container_root)
            os.chdir('/')
        except Exception as err:  # pylint: disable=broad-except
            event = traceevents.AbortedTraceEvent(
                instanceid=app['name'],
                why=app_abort.AbortedReason.PIVOT_ROOT.value,
                payload=str(err),
            )

            _abort(event, container_root)

            # reraise err to exit start_container
            raise err

        # XXX: Debug info
        _LOGGER.debug('Current mounts: %s',
                      pprint.pformat(fs_linux.list_mounts()))

        subproc.safe_exec(['/services/services.init'])

    return start_container
