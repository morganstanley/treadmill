"""Starts a Treadmill spawn process."""

import logging
import os
import sys
import tempfile
import traceback

import click
import treadmill
from treadmill.spawn import instance
from treadmill.spawn import manifest_watch
from treadmill.spawn import utils
import yaml

_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler."""

    @click.group(name='spawn')
    def spawn_grp():
        """Spawn group."""
        log_conf_file = os.path.join(treadmill.TREADMILL, 'etc', 'logging',
                                     'spawn.yml')
        try:
            with open(log_conf_file, 'r') as fh:
                log_config = yaml.load(fh)
                logging.config.dictConfig(log_config)

        except IOError:
            with tempfile.NamedTemporaryFile(delete=False) as f:
                traceback.print_exc(file=f)
                click.echo('Unable to load log conf: %s [ %s ]' %
                           (log_conf_file, f.name), err=True)

    @spawn_grp.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    def watch(approot):
        """Spawn manifest watch process."""
        watcher = manifest_watch.ManifestWatch(approot)
        dirwatch = watcher.get_dir_watch()

        watcher.sync()

        while True:
            if dirwatch.wait_for_events(60):
                dirwatch.process_events()

    @spawn_grp.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.argument('manifest_path', type=click.Path(exists=True), nargs=1)
    def run(approot, manifest_path):
        """Spawn instance run process."""
        inst = instance.Instance(approot, manifest_path)

        if inst.manifest is None:
            _LOGGER.error('No manifest found')
            sys.exit(1)

        sock = utils.open_socket(inst.id)
        if sock is None:
            _LOGGER.error('Could not open socket %r', inst.id)
            sys.exit(2)

        if not inst.run():
            _LOGGER.error('TM run failed')
            sys.exit(3)

        # Redirect STDIN and original STDOUT to socket
        os.dup2(sock.fileno(), sys.stdin.fileno())
        os.dup2(sock.fileno(), sys.stdout.fileno())

        # Now wait on event
        utils.exec_fstrace(inst.get_watch_path())

    @spawn_grp.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.argument('manifest_path', type=click.Path(exists=True), nargs=1)
    @click.argument('exit_code', type=int, nargs=1)
    def finish(approot, manifest_path, exit_code):
        """Spawn instance finish process."""
        inst = instance.Instance(approot, manifest_path)

        inst.stop(exit_code)
        inst.remove_manifest()

    del watch
    del run
    del finish
    return spawn_grp
