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
from treadmill import pivot_root
from treadmill import trace

from treadmill.appcfg import abort as app_abort
from treadmill.appcfg import manifest as app_manifest
from treadmill.trace.app import events as traceevents

_LOGGER = logging.getLogger(__name__)


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


def init():
    """Top level command handler."""
    @click.command(name='start-container')
    @click.option('--container-root', type=click.Path(exists=True),
                  required=True)
    @click.argument('manifest', type=click.Path(exists=True))
    def start_container(container_root, manifest):
        """Treadmill container boot process.
        """
        _LOGGER.info('Initializing container: %s', container_root)
        app = app_manifest.read(manifest)

        try:
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

        # Clean the environ
        # TODO: Remove me once clean environment management is merged in.
        os.environ.pop('PYTHONPATH', None)
        os.environ.pop('LC_ALL', None)
        os.environ.pop('LANG', None)

        # Clear aliases path.
        os.environ.pop('TREADMILL_ALIASES_PATH', None)

        subproc.safe_exec(
            [
                's6_svscan',
                '-s',
                '/services'
            ]
        )

    return start_container
