"""Manages Treadmill applications lifecycle.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import logging
import os
import shutil

from treadmill import appcfg
from treadmill import fs
from treadmill import supervisor
from treadmill import trace
from treadmill import utils
from treadmill import subproc

from treadmill.appcfg import manifest as app_manifest
from treadmill.trace.app import events
from treadmill import runtime as app_runtime

_LOGGER = logging.getLogger(__name__)


def load_runtime_manifest(tm_env, event, runtime):
    """load manifest data and modify based on runtime
    :param tm_env:
        Full path to the application node event in the zookeeper cache.
     :type event:
        ``treadmill.appenv.AppEnvironment``
    :param event:
        Full path to the application node event in the zookeeper cache.
    :type event:
        ``str``
    :param runtime:
        The name of the runtime to use.
    :type runtime:
        ``str``
    :return:
        Application manifest object
    :rtype:
        ``dict``
    """
    manifest_data = app_manifest.load(event)

    # apply runtime manipulation on manifest data
    runtime_cls = app_runtime.get_runtime_cls(runtime)
    runtime_cls.manifest(tm_env, manifest_data)

    app_manifest.add_manifest_features(manifest_data, runtime_cls.name, tm_env)

    # TODO: This is HORRIBLE hack.
    #       The code inside "cls".manifest used to create a copy of service
    #       environment (manifest environ + svc environ).
    #
    #       As such, any later changes to environment that were added by
    #       loaded features did not have any effect.
    #
    #       Service startup need to honor proper environment hierarchy. Load
    #       "treadmill" envdif, then envdir of the container, then per svc.
    #
    #       Need to move on, so making this change for now.
    for svc in manifest_data['services']:
        assert isinstance(manifest_data['environ'], list)
        assert isinstance(svc['environ'], list)
        svc['environ'] = manifest_data['environ'] + svc['environ']

    return manifest_data


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
        manifest_data = load_runtime_manifest(tm_env, event, runtime)
    except IOError:
        # File is gone. Nothing to do.
        _LOGGER.exception('No event to load: %r', event)
        return None

    # Freeze the app data into a namedtuple object
    app = utils.to_obj(manifest_data)

    # Generate a unique name for the app
    uniq_name = appcfg.app_unique_name(app)

    # Write the actual container start script
    if os.name == 'nt':
        run_script = '{treadmill}/scripts/treadmill sproc run .'.format(
            treadmill=subproc.resolve('treadmill'),
        )
    else:
        run_script = 'exec {treadmill}/bin/treadmill sproc run ../'.format(
            treadmill=subproc.resolve('treadmill'),
        )

    # Create the service for that container
    container_svc = supervisor.create_service(
        tm_env.apps_dir,
        name=uniq_name,
        app_run_script=run_script,
        userid='root',
        downed=False,
        monitor_policy={
            'limit': 0,
            'interval': 60,
            'tombstone': {
                'uds': False,
                'path': tm_env.running_tombstone_dir,
                'id': app.name
            }
        },
        environ={},
        environment=app.environment
    )
    data_dir = container_svc.data_dir

    # Copy the original event as 'manifest.yml' in the container dir
    try:
        shutil.copyfile(
            event,
            os.path.join(data_dir, 'manifest.yml')
        )
    except IOError as err:
        # File is gone, cleanup.
        if err.errno == errno.ENOENT:
            shutil.rmtree(container_svc.directory)
            _LOGGER.exception('Event gone: %r', event)
            return None
        else:
            raise

    # Store the app.json in the container directory
    fs.write_safe(
        os.path.join(data_dir, appcfg.APP_JSON),
        lambda f: f.writelines(
            utils.json_genencode(manifest_data)
        ),
        mode='w',
        permission=0o644
    )

    trace.post(
        tm_env.app_events_dir,
        events.ConfiguredTraceEvent(
            instanceid=app.name,
            uniqueid=app.uniqueid
        )
    )

    return container_svc.directory
