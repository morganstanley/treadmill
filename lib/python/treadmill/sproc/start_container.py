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

_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler."""
    @click.command(name='start-container')
    @click.option('--container-root', type=click.Path(exists=True),
                  required=True)
    def start_container(container_root):
        """Treadmill container boot process.
        """
        _LOGGER.info('Initializing container: %s', container_root)

        # TODO: we need to abort container if pivot_root.make_root fails
        # To send abort event to /run/tm_ctl/appevents
        pivot_root.make_root(container_root)
        os.chdir('/')

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
