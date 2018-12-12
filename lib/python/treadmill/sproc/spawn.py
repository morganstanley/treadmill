"""Starts a Treadmill spawn process.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click
from treadmill.spawn import manifest_watch
from treadmill.spawn import cleanup
from treadmill.spawn import tree as spawn_tree


_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler."""

    @click.group(name='spawn')
    def spawn_grp():
        """Spawn group.
        """

    @spawn_grp.command(name='watch_manifest')
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    def watch_manifest_cmd(approot):
        """Spawn manifest watch process."""
        watch = manifest_watch.ManifestWatch(approot)
        dirwatch = watch.get_dir_watch()

        watch.sync()

        while True:
            if dirwatch.wait_for_events(60):
                dirwatch.process_events()

    @spawn_grp.command(name='cleanup')
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    def cleanup_cmd(approot):
        """Spawn cleanup process."""
        watch = cleanup.Cleanup(approot)
        dirwatch = watch.get_dir_watch()

        watch.sync()

        while True:
            if dirwatch.wait_for_events(60):
                dirwatch.process_events()

    @spawn_grp.command(name='start_tree')
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    def start_tree_cmd(approot):
        """Starts the spawn tree."""
        tree = spawn_tree.Tree(approot)
        tree.create()
        tree.run()

    del watch_manifest_cmd
    del cleanup_cmd
    del start_tree_cmd
    return spawn_grp
