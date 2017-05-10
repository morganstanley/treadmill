"""Cgroup management service."""


import errno
import logging
import os
import select

from .. import cgroups
from .. import cgutils
from .. import logcontext as lc
from .. import sysinfo
from .. import utils
from .. import supervisor

from ._base_service import BaseResourceServiceImpl

_LOGGER = lc.ContainerAdapter(logging.getLogger(__name__))


class CgroupResourceService(BaseResourceServiceImpl):
    """Cgroup service implementation.
    """

    __slots__ = (
        '_cgroups',
        '_apps_dir',
    )

    SUBSYSTEMS = ('cpu', 'cpuacct', 'memory', 'blkio')

    PAYLOAD_SCHEMA = (('memory', True, str),
                      ('cpu', True, int))

    def __init__(self, apps_dir):
        super(CgroupResourceService, self).__init__()
        self._apps_dir = apps_dir
        self._cgroups = {}

    def initialize(self, service_dir):
        super(CgroupResourceService, self).initialize(service_dir)
        # NOTE(boysson): We assume cgroup initialization is done by cginit
        #                during node startup. Otherwise it would need to be
        #                done here.

    def synchronize(self):
        # NOTE(boysson): We assume cgroup initialization is done by cginit
        #                during node startup. Otherwise this would need to be
        #                implemented.
        pass

    def report_status(self):
        # TODO: Once more cgroup responsibilities are handed over to
        #                this service, there should be more information
        #                published here.
        return {'ready': True}

    def event_handlers(self):
        return [
            (handler['fd'], select.POLLIN, handler['oom_handler'])
            for handler in self._cgroups.values()
            if handler['fd'] != -1
        ]

    def on_create_request(self, rsrc_id, rsrc_data):
        instance_id = rsrc_id
        memory_limit = rsrc_data['memory']
        cpu_limit = rsrc_data['cpu']

        cgrp = os.path.join('treadmill', 'apps', instance_id)

        with lc.LogContext(_LOGGER, rsrc_id) as log:
            log.logger.info('Creating cgroups: %s:%s', self.SUBSYSTEMS, cgrp)
            for subsystem in self.SUBSYSTEMS:
                cgroups.create(subsystem, cgrp)

            # blkio settings
            #
            cgroups.set_value('blkio', cgrp, 'blkio.weight', 100)

            # memory settings
            #
            self._register_oom_handler(cgrp, instance_id)

            cgroups.set_value('memory', cgrp,
                              'memory.soft_limit_in_bytes', memory_limit)

            # TODO: set hardlimit to app.memory and comment the
            #                reset_memory block until proper solution for
            #                cgroup race condition is implemented.
            cgutils.set_memory_hardlimit(cgrp, memory_limit)

            # expunged = cgutils.reset_memory_limit_in_bytes()
            # for expunged_uniq_name in expunged:
            #     exp_app_dir = os.path.join(tm_env.apps_dir,
            #                                expunged_uniq_name)
            #     with open(os.path.join(exp_app_dir,
            #                            'services', 'finished'), 'w') as f:
            #         f.write('oom')
            #     exp_cgrp = os.path.join('treadmill', 'apps',
            #                             expunged_uniq_name)
            #     cgutils.kill_apps_in_cgroup('memory', exp_cgrp, delete=False)

            # cpu settings
            #

            # Calculate the value of cpu shares for the app.
            #
            # [treadmill/apps/cpu.shares] = <total bogomips allocated to TM>
            #
            # [treadmill/apps/<app>/cpu.shares] = app.cpu * BMIPS_PER_CPU
            #
            app_cpu_pcnt = utils.cpu_units(cpu_limit) / 100.
            app_bogomips = app_cpu_pcnt * sysinfo.BMIPS_PER_CPU
            app_cpu_shares = int(app_bogomips)

            log.logger.info(
                'created in cpu:%s with %s shares', cgrp, app_cpu_shares
            )
            cgroups.set_cpu_shares(cgrp, app_cpu_shares)

        return {
            subsystem: cgrp
            for subsystem in self.SUBSYSTEMS
        }

    def on_delete_request(self, rsrc_id):
        instance_id = rsrc_id
        cgrp = os.path.join('treadmill/apps', instance_id)

        with lc.LogContext(_LOGGER, rsrc_id) as log:
            self._unregister_oom_handler(cgrp)

            log.logger.info('Deleting cgroups: %s:%s', self.SUBSYSTEMS, cgrp)
            for subsystem in self.SUBSYSTEMS:
                cgroups.delete(subsystem, cgrp)

        # Recalculate the cgroup hard limits on remaining apps
        #
        # TODO: commented out until proper fix implemented.
        #
        # expunged = cgutils.reset_memory_limit_in_bytes()
        # for expunged_uniq_name in expunged:
        #     exp_app_dir = os.path.join(tm_env.apps_dir, expunged_uniq_name)
        #     with open(os.path.join(exp_app_dir,
        #                            'services', 'finished'), 'w') as f:
        #         f.write('oom')
        #     exp_cgrp = os.path.join('treadmill', 'apps', expunged_uniq_name)
        #     cgutils.kill_apps_in_cgroup('memory', exp_cgrp, delete=False)

        return True

    def _register_oom_handler(self, cgrp, instance_id):
        """Register a handler for OOM events in a cgroup.
        """
        if cgrp in self._cgroups:
            # No need to register if already present
            return

        fd = cgutils.get_memory_oom_eventfd(cgrp)

        handler_data = {
            'fd': fd,
            'cgroup': cgrp,
            'instance_id': instance_id,
            'oom_handler': None,
        }

        def _cgroup_oom_handler():
            """Simple OOM handler that shuts down the container.
            """
            if handler_data['fd'] != -1:
                _LOGGER.warning('OOM event on %r, killing container',
                                handler_data['instance_id'])

                # Kill container
                _shutdown_container(instance_id, self._apps_dir)

                try:
                    os.close(handler_data['fd'])
                except OSError as err:
                    if err.errno == errno.EBADF:
                        _LOGGER.warning('While closing %r: %r',
                                        handler_data['instance_id'], err)

                handler_data['fd'] = -1

                # We need a refresh after this event
                return True

        handler_data['oom_handler'] = _cgroup_oom_handler
        self._cgroups[cgrp] = handler_data
        _LOGGER.info('Registered OOM watcher on %r', cgrp)

    def _unregister_oom_handler(self, cgrp):
        """Unregister a handler for OOM events in a cgroup.
        """
        handler_data = self._cgroups.pop(cgrp, None)
        if handler_data is None:
            # Nothing to do
            return

        if handler_data['fd'] != -1:
            os.close(handler_data['fd'])
            handler_data['fd'] = -1

        _LOGGER.info('Unregistered OOM watcher on %r',
                     cgrp)


def _shutdown_container(instance_id, apps_dir):
    """Shutdown a container.
    """
    # TODO: This is the wrong place for this knowledge
    instance_sys = os.path.join(
        apps_dir,
        instance_id,
        'sys',
    )
    supervisor.stop_service(
        instance_sys,
        'start_container'
    )
