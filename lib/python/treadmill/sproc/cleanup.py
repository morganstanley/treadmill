"""Runs the Treadmill container cleanup job."""
from __future__ import absolute_import

import glob
import logging
import os
import subprocess

import click

from .. import appmgr
from .. import dirwatch
from .. import logcontext as lc
from .. import subproc

import treadmill

_LOGGER = lc.ContainerAdapter(logging.getLogger(__name__))

# FIXME(boysson): This extremely high timeout value comes from the fact that we
#                 have a very high watchdog value in appmgr.finish.
_WATCHDOG_HEARTBEAT_SEC = 5 * 60

# Maximum number of cleanup request to process per cycle. Be careful of
# watchdog timeouts when increasing this value.
_MAX_REQUEST_PER_CYCLE = 1

_SERVICE_NAME = 'Cleanup'


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    def top(approot):
        """Start cleanup process."""
        app_env = appmgr.AppEnvironment(root=approot)

        # Setup the watchdog
        watchdog_lease = app_env.watchdogs.create(
            name='svc-{svc_name}'.format(svc_name=_SERVICE_NAME),
            timeout='{hb:d}s'.format(hb=_WATCHDOG_HEARTBEAT_SEC),
            content='Service {svc_name!r} failed'.format(
                svc_name=_SERVICE_NAME),
        )

        def _on_created(path):
            """Callback invoked with new cleanup file appears."""
            fullpath = os.path.join(app_env.cleanup_dir, path)
            with lc.LogContext(_LOGGER, os.path.basename(path),
                               lc.ContainerAdapter) as log:
                if not os.path.islink(fullpath):
                    log.info('Ignore - not a link: %s', fullpath)
                    return

                container_dir = os.readlink(fullpath)
                log.info('Cleanup: %s => %s', path, container_dir)
                if os.path.exists(container_dir):

                    treadmill_bin = os.path.join(
                        treadmill.TREADMILL,
                        'bin',
                        'treadmill'
                    )

                    try:
                        log.info('invoking treadmill_bin script: %r',
                                 treadmill_bin)
                        subproc.check_call(
                            [
                                treadmill_bin,
                                'sproc',
                                'finish',
                                container_dir
                            ]
                        )
                    except subprocess.CalledProcessError as _err:
                        log.exception('Fatal error running %r.', treadmill_bin)
                        raise

                else:
                    log.info('Container dir does not exist: %r', container_dir)

                os.unlink(fullpath)

        watcher = dirwatch.DirWatcher(app_env.cleanup_dir)
        watcher.on_created = _on_created

        # Before starting, capture all already pending cleanups
        leftover = glob.glob(os.path.join(app_env.cleanup_dir, '*'))
        # and "fake" a created event on all of them
        for pending_cleanup in leftover:
            _on_created(pending_cleanup)

        loop_timeout = _WATCHDOG_HEARTBEAT_SEC/2
        while True:
            if watcher.wait_for_events(timeout=loop_timeout):
                watcher.process_events(max_events=_MAX_REQUEST_PER_CYCLE)

            # Heartbeat
            watchdog_lease.heartbeat()

        _LOGGER.info('Cleanup service shutdown.')
        watchdog_lease.remove()

    return top
