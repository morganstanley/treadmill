"""Runs the Treadmill container cleanup job.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import click

from treadmill import appenv
from treadmill import dirwatch
from treadmill import logcontext as lc
from treadmill import runtime as app_runtime

if os.name == 'nt':
    import treadmill.syscall.winsymlink  # pylint: disable=W0611

_LOGGER = lc.ContainerAdapter(logging.getLogger(__name__))

# FIXME: This extremely high timeout value comes from the fact that we
#        have a very high watchdog value in runtime.
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
    @click.option('--runtime', envvar='TREADMILL_RUNTIME', required=True)
    def top(approot, runtime):
        """Start cleanup process."""
        tm_env = appenv.AppEnvironment(root=approot)

        # Setup the watchdog
        watchdog_lease = tm_env.watchdogs.create(
            name='svc-{svc_name}'.format(svc_name=_SERVICE_NAME),
            timeout='{hb:d}s'.format(hb=_WATCHDOG_HEARTBEAT_SEC),
            content='Service {svc_name!r} failed'.format(
                svc_name=_SERVICE_NAME),
        )

        def _on_created(path):
            """Callback invoked with new cleanup file appears."""
            fullpath = os.path.join(tm_env.cleanup_dir, path)
            with lc.LogContext(_LOGGER, os.path.basename(path),
                               lc.ContainerAdapter) as log:
                if not os.path.islink(fullpath):
                    log.info('Ignore - not a link: %s', fullpath)
                    return

                container_dir = os.readlink(fullpath)
                log.info('Cleanup: %s => %s', path, container_dir)
                if os.path.exists(container_dir):
                    with lc.LogContext(_LOGGER,
                                       os.path.basename(container_dir),
                                       lc.ContainerAdapter) as log:
                        try:
                            app_runtime.get_runtime(runtime, tm_env,
                                                    container_dir).finish()
                        except Exception:  # pylint: disable=W0703
                            if not os.path.exists(container_dir):
                                log.info('Container dir does not exist: %s',
                                         container_dir)
                            else:
                                log.exception('Fatal error running finish %r.',
                                              container_dir)
                                raise

                else:
                    log.info('Container dir does not exist: %r', container_dir)

                os.unlink(fullpath)

        watcher = dirwatch.DirWatcher(tm_env.cleanup_dir)
        watcher.on_created = _on_created

        loop_timeout = _WATCHDOG_HEARTBEAT_SEC // 2
        while True:
            if watcher.wait_for_events(timeout=loop_timeout):
                watcher.process_events(max_events=_MAX_REQUEST_PER_CYCLE)

            # Heartbeat
            watchdog_lease.heartbeat()

        _LOGGER.info('Cleanup service shutdown.')
        watchdog_lease.remove()

    return top
