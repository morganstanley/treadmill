"""Manages Treadmill applications lifecycle.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import shutil
import sys

from treadmill import appcfg
from treadmill import appevents
from treadmill import dist
from treadmill import fs
from treadmill import supervisor
from treadmill import utils

from treadmill.appcfg import manifest as app_manifest
from treadmill.apptrace import events

_LOGGER = logging.getLogger(__name__)


def configure(tm_env, event, runtime):
    """Creates directory necessary for starting the application.

    This operation is idem-potent (it can be repeated).

    The directory layout is::

        - (treadmill root)/
          - apps/
            - (app unique name)/
              - data/
                - app_start
                - app.json
                - manifest.yml
                - policy.json
                env/
                - TREADMILL_*
                run
                finish
                log/
                - run

    The 'run' script is responsible for creating container environment
    and starting the container.

    The 'finish' script is invoked when container terminates and will
    deallocate any resources (NAT rules, etc) that were allocated for the
    container.
    """
    # Load the app from the event
    try:
        manifest_data = app_manifest.load(tm_env, event, runtime)
    except IOError:
        # File is gone. Nothing to do.
        _LOGGER.exception('No event to load: %r', event)
        return

    # Freeze the app data into a namedtuple object
    app = utils.to_obj(manifest_data)

    # Generate a unique name for the app
    uniq_name = appcfg.app_unique_name(app)

    # Write the actual container start script
    if os.name == 'nt':
        run_script = ' '.join([
            sys.executable, '-m', 'treadmill.ms', 'sproc', 'run', '.'
        ])
    else:
        run_script = ' '.join([
            'exec', dist.TREADMILL_BIN, 'sproc', 'run', '../'
        ])

    # Create the service for that container
    container_svc = supervisor.create_service(
        tm_env.apps_dir,
        name=uniq_name,
        app_run_script=run_script,
        userid='root',
        downed=False,
        monitor_policy={'limit': 0, 'interval': 60},
        environ={},
        environment=app.environment
    )
    data_dir = container_svc.data_dir

    # Copy the original event as 'manifest.yml' in the container dir
    shutil.copyfile(
        event,
        os.path.join(data_dir, 'manifest.yml')
    )

    # Store the app.json in the container directory
    fs.write_safe(
        os.path.join(data_dir, appcfg.APP_JSON),
        lambda f: f.writelines(
            utils.json_genencode(manifest_data)
        ),
        mode='w',
        permission=0o644
    )

    appevents.post(
        tm_env.app_events_dir,
        events.ConfiguredTraceEvent(
            instanceid=app.name,
            uniqueid=app.uniqueid
        )
    )

    return container_svc.directory
