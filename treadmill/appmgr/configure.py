"""Manages Treadmill applications lifecycle."""


import pwd

import errno
import logging
import os
import shutil
import tempfile

import yaml

import treadmill
from treadmill import appevents
from treadmill import appmgr
from treadmill import utils

from treadmill.apptrace import events

from . import manifest as app_manifest


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

    # Check the identity we are going to run as. It needs to exists on the host
    # or we will fail later on as we try to seteuid.
    try:
        pwd.getpwnam(app.proid)

    except KeyError:
        _LOGGER.exception('Unable to find proid %r in passwd database.',
                          app.proid)
        raise

    # Generate a unique name for the app
    uniq_name = appmgr.app_unique_name(app)

    # Create the app's running directory
    container_dir = os.path.join(tm_env.apps_dir, uniq_name)

    # We assume it is a 'resume' if the container directory already exists.
    is_resume = False
    try:
        os.makedirs(container_dir)
    except OSError as err:
        if err.errno == errno.EEXIST:
            _LOGGER.info('Resuming container %r', uniq_name)
            is_resume = True
        else:
            raise

    # Copy the event as 'manifest.yml' in the container dir
    shutil.copyfile(
        event,
        os.path.join(container_dir, 'manifest.yml')
    )

    # Setup the service clients
    cgroup_client = tm_env.svc_cgroup.make_client(
        os.path.join(container_dir, 'cgroups')
    )
    localdisk_client = tm_env.svc_localdisk.make_client(
        os.path.join(container_dir, 'localdisk')
    )
    network_client = tm_env.svc_network.make_client(
        os.path.join(container_dir, 'network')
    )

    # Store the app int the container_dir
    app_yml = os.path.join(container_dir, _APP_YML)
    with open(app_yml, 'w') as f:
        yaml.dump(manifest_data, stream=f)

    # Generate resources requests

    # Cgroup
    cgroup_req = {
        'memory': app.memory,
        'cpu': app.cpu,
    }
    # Local Disk
    localdisk_req = {
        'size': app.disk,
    }
    # Network
    network_req = {
        'environment': app.environment,
    }

    if not is_resume:
        cgroup_client.create(uniq_name, cgroup_req)
        localdisk_client.create(uniq_name, localdisk_req)

    else:
        cgroup_client.update(uniq_name, cgroup_req)
        localdisk_client.update(uniq_name, localdisk_req)

    if not app.shared_network:
        if not is_resume:
            network_client.create(uniq_name, network_req)
        else:
            network_client.update(uniq_name, network_req)

    # Mark the container as defaulting to down state
    utils.touch(os.path.join(container_dir, 'down'))

    # Generate the supervisor's run script
    app_run_cmd = ' '.join([
        treadmill.TREADMILL_BIN,
        'sproc', 'run', container_dir
    ])

    run_out_file = os.path.join(container_dir, 'run.out')

    utils.create_script(os.path.join(container_dir, 'run'),
                        'supervisor.run_no_log',
                        log_out=run_out_file,
                        cmd=app_run_cmd)

    _init_log_file(run_out_file,
                   os.path.join(tm_env.apps_dir, "%s.run.out" % uniq_name))

    # Unique name for the link, based on creation time.
    cleanup_link = os.path.join(tm_env.cleanup_dir, uniq_name)
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


def schedule(container_dir, running_link):
    """Kick start the container by placing it in the running folder.
    """
    # NOTE(boysson): We use a temporary file + rename behavior to override any
    #                potential old symlinks.
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
