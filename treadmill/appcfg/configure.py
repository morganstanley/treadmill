"""Manages Treadmill applications lifecycle.
"""

import errno
import logging
import os
import shutil
import tempfile

import yaml

import treadmill
from treadmill import appevents
from treadmill import appcfg
from treadmill import fs
from treadmill import osnoop
from treadmill import utils

from treadmill.appcfg import manifest as app_manifest
from treadmill.apptrace import events

if os.name == 'posix':
    import pwd

_LOGGER = logging.getLogger(__name__)

_APP_YML = 'app.yml'


def configure(tm_env, event):
    """Creates directory necessary for starting the application.

    This operation is idem-potent (it can be repeated).

    The directory layout is::

        - (treadmill root)
          - apps
            - (app unique name)
              - app.yml
                run
                finish
                log/run

    The 'run' script is responsible for creating container environment
    and starting svscan inside the container.

    The 'finish' script is invoked when container terminates and will
    deallocate any resources (NAT rules, etc) that were allocated for the
    container.
    """
    # R0915: Need to refactor long function into smaller pieces.
    #
    # pylint: disable=R0915

    # Load the app from the event
    try:
        manifest_data = app_manifest.load(tm_env, event)
    except IOError:
        # File is gone. Nothing to do.
        _LOGGER.exception("No event to load: %r", event)
        return

    # Freeze the app data into a namedtuple object
    app = utils.to_obj(manifest_data)

    # Check the identity we are going to run as
    _check_identity(app.proid)

    # Generate a unique name for the app
    uniq_name = appcfg.app_unique_name(app)

    # Create the app's running directory
    container_dir = os.path.join(tm_env.apps_dir, uniq_name)

    if not fs.mkdir_safe(container_dir):
        _LOGGER.info('Resuming container %r', uniq_name)

    # Copy the event as 'manifest.yml' in the container dir
    shutil.copyfile(
        event,
        os.path.join(container_dir, 'manifest.yml')
    )

    # Store the app int the container_dir
    app_yml = os.path.join(container_dir, _APP_YML)
    with open(app_yml, 'w') as f:
        yaml.dump(manifest_data, stream=f)

    # Mark the container as defaulting to down state
    utils.touch(os.path.join(container_dir, 'down'))

    # Generate the supervisor's run script
    app_run_cmd = ' '.join([
        treadmill.TREADMILL_BIN,
        'sproc', 'run', container_dir
    ])

    utils.create_script(os.path.join(container_dir, 'run'),
                        'supervisor.run_no_log',
                        cmd=app_run_cmd)

    fs.mkdir_safe(os.path.join(container_dir, 'log'))
    utils.create_script(os.path.join(container_dir, 'log', 'run'),
                        'logger.run')

    # Unique name for the link, based on creation time.
    cleanup_link = os.path.join(tm_env.cleanup_dir, uniq_name)
    if os.name == 'nt':
        finish_cmd = '%%COMSPEC%% /C mklink /D %s %s' % \
                     (cleanup_link, container_dir)
    else:
        finish_cmd = '/bin/ln -snvf %s %s' % (container_dir, cleanup_link)

    utils.create_script(os.path.join(container_dir, 'finish'),
                        'supervisor.finish',
                        service=app.name, proid=None,
                        cmds=[finish_cmd])

    appevents.post(
        tm_env.app_events_dir,
        events.ConfiguredTraceEvent(
            instanceid=app.name,
            uniqueid=app.uniqueid
        )
    )
    return container_dir


@osnoop.windows
def _check_identity(proid):
    """Check the identity we are going to run as."""
    # It needs to exist on the host or will fail later on as we try to seteuid.
    try:
        pwd.getpwnam(proid)

    except KeyError:
        _LOGGER.exception('Unable to find proid %r in passwd database.',
                          proid)
        raise


def schedule(container_dir, running_link):
    """Kick start the container by placing it in the running folder.
    """
    # NOTE: We use a temporary file + rename behavior to override any
    #       potential old symlinks.
    tmpfile = tempfile.mktemp()
    os.symlink(container_dir, tmpfile)
    os.rename(tmpfile, running_link)


def _init_log_file(log_file, link_path):
    """Generate log file and provide hard link in other place
    """
    utils.touch(log_file)
    try:
        os.link(log_file, link_path)
    except OSError as err:
        if err.errno == errno.EEXIST:
            _LOGGER.debug("Linked log file already exists.")
        else:
            raise
