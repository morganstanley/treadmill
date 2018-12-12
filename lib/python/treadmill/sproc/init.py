"""Treadmill initialization and server presence daemon.

This service register the node into the Treadmill cell and, as such, is
responsible for publishing the node's capacity to the scheduler.

This service is also responsible for shutting down the node, when necessary or
requested, by disabling all traffic from and to the containers.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import functools
import logging
import os
import time

import kazoo
import click

from treadmill import appenv
from treadmill import context
from treadmill import netdev
from treadmill import postmortem
from treadmill import supervisor
from treadmill import sysinfo
from treadmill import traits
from treadmill import utils
from treadmill import version
from treadmill import zknamespace as z
from treadmill import zkutils

if os.name == 'posix':
    from treadmill import iptables

_LOGGER = logging.getLogger(__name__)

_WATCHDOG_CHECK_INTERVAL = 30


def init():
    """Top level command handler."""
    @click.command()
    @click.option('--exit-on-fail', is_flag=True, default=False)
    @click.option('--zkid', help='Zookeeper session ID file.')
    @click.option('--notification-fd', help='Notification file descriptor.',
                  type=int)
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('--runtime', envvar='TREADMILL_RUNTIME', required=True)
    @click.pass_context
    def top(ctx, exit_on_fail, zkid, notification_fd, approot, runtime):
        """Run treadmill init process."""
        _LOGGER.info('Initializing Treadmill: %s (%s)', approot, runtime)

        tm_env = appenv.AppEnvironment(approot)
        stop_on_lost = functools.partial(_stop_on_lost, tm_env)
        zkclient = zkutils.connect(context.GLOBAL.zk.url,
                                   idpath=zkid,
                                   listener=stop_on_lost)

        while not zkclient.exists(z.SERVER_PRESENCE):
            _LOGGER.warning('namespace not ready.')
            time.sleep(30)

        hostname = sysinfo.hostname()

        zk_blackout_path = z.path.blackedout_server(hostname)
        zk_server_path = z.path.server(hostname)
        zk_presence_path = z.path.server_presence(hostname)

        while not zkclient.exists(zk_server_path):
            _LOGGER.warning('server %s not defined in the cell.', hostname)
            time.sleep(30)

        _LOGGER.info('Checking blackout list.')
        blacklisted = bool(zkclient.exists(zk_blackout_path))

        root_cgroup = ctx.obj['ROOT_CGROUP']
        os_args = {}
        if os.name == 'posix':
            os_args['cgroup_prefix'] = root_cgroup

        if not blacklisted:
            # Node startup.
            _node_start(tm_env, runtime, zkclient, hostname, zk_server_path,
                        zk_presence_path, os_args)

            utils.report_ready(notification_fd)

            _init_network()

            _start_init1(tm_env)
            _LOGGER.info('Ready.')

            down_reason = _main_loop(tm_env, zkclient, zk_presence_path)

            if down_reason is not None:
                _LOGGER.warning('Shutting down: %s', down_reason)
                # Blackout the server.
                zkutils.ensure_exists(
                    zkclient,
                    zk_blackout_path,
                    acl=[zkclient.make_host_acl(hostname, 'rwcda')],
                    data=down_reason
                )
                trigger_postmortem = True
            else:
                # Blacked out manually
                trigger_postmortem = bool(zkclient.exists(zk_blackout_path))

            if trigger_postmortem:
                postmortem.run(approot, root_cgroup)

        else:
            # Node was already blacked out.
            _LOGGER.warning('Shutting down blacked out node.')

        # This is the shutdown phase.

        # Delete the node
        if zk_presence_path:
            zkutils.ensure_deleted(zkclient, zk_presence_path)
        zkclient.remove_listener(stop_on_lost)
        zkclient.stop()
        zkclient.close()

        _cleanup_network()

        # to ternminate all the running apps
        _blackout_terminate(tm_env)

        if exit_on_fail:
            utils.sys_exit(-1)
        else:
            # Sit forever in a broken state
            while True:
                time.sleep(1000000)

    return top


def _blackout_terminate(tm_env):
    """Blackout by terminating all containers in running dir.
    """
    _LOGGER.info('Terminating monitor.')
    supervisor.control_service(
        os.path.join(tm_env.init_dir, 'monitor'),
        supervisor.ServiceControlAction.down,
        wait=supervisor.ServiceWaitAction.down
    )

    _LOGGER.info('Terminating init1.')
    supervisor.control_service(
        os.path.join(tm_env.init_dir, 'start_init1'),
        supervisor.ServiceControlAction.down,
        wait=supervisor.ServiceWaitAction.down
    )


def _start_init1(tm_env):
    """Start init1 supervision."""
    _LOGGER.info('Starting init1.')
    supervisor.control_service(
        os.path.join(tm_env.init_dir, 'start_init1'),
        supervisor.ServiceControlAction.up,
        wait=supervisor.ServiceWaitAction.up
    )


def _init_network():
    """Initialize network.
    """
    if os.name == 'nt':
        return

    # (Re)Enable IP forwarding
    netdev.dev_conf_forwarding_set('tm0', True)


def _cleanup_network():
    """Cleanup network.
    """
    if os.name == 'nt':
        return

    # Disable network traffic from and to the containers.
    netdev.dev_conf_forwarding_set('tm0', False)


def _node_start(tm_env, runtime, zkclient, hostname,
                zk_server_path, zk_presence_path, os_args):
    """Node startup. Try to re-establish old session or start fresh.
    """
    old_session_ok = False
    try:
        _data, metadata = zkclient.get(zk_presence_path)
        if metadata.owner_session_id == zkclient.client_id[0]:
            _LOGGER.info('Reconnecting with previous session: %s',
                         metadata.owner_session_id)
            old_session_ok = True
        else:
            _LOGGER.info('Session id does not match, new session.')
            zkclient.delete(zk_presence_path)
    except kazoo.client.NoNodeError:
        _LOGGER.info('%s does not exist.', zk_presence_path)

    if not old_session_ok:
        _node_initialize(tm_env, runtime,
                         zkclient, hostname,
                         zk_server_path, zk_presence_path, os_args)


def _node_initialize(tm_env, runtime, zkclient, hostname,
                     zk_server_path, zk_presence_path, os_args):
    """Node initialization. Should only be done on a cold start.
    """
    try:
        new_node_info = sysinfo.node_info(tm_env, runtime, **os_args)

        traitz = zkutils.get(zkclient, z.path.traits())
        new_node_info['traits'] = traits.detect(traitz)

        # Merging scheduler data with node_info data
        node_info = zkutils.get(zkclient, zk_server_path)
        node_info.update(new_node_info)
        _LOGGER.info('Registering node: %s: %s, %r',
                     zk_server_path, hostname, node_info)

        zkutils.update(zkclient, zk_server_path, node_info)
        host_acl = zkclient.make_host_acl(hostname, 'rwcda')
        _LOGGER.debug('host_acl: %r', host_acl)
        zkutils.put(zkclient,
                    zk_presence_path, {'seen': False},
                    acl=[host_acl],
                    ephemeral=True)

        # TODO: Fix the network initialization. Then the below can be part of
        # appenv.initialize()
        if os.name == 'posix':
            # Flush all rules in iptables nat and mangle tables (it is assumed
            # that none but Treadmill manages these tables) and bulk load all
            # the Treadmill static rules
            iptables.initialize(node_info['network']['external_ip'])

        node_version = version.get_version()
        if zkclient.exists(z.VERSION) and zkclient.exists(z.VERSION_HISTORY):
            _LOGGER.info('Registering node version: %r', node_version)
            version.save_version(zkclient, hostname, node_version)
        else:
            _LOGGER.warning(
                'Unable to register node version, namespace not ready: %r',
                node_version
            )

    except Exception:  # pylint: disable=W0703
        _LOGGER.exception('Node initialization failed')
        zkclient.stop()


def _stop_on_lost(tm_env, state):
    _LOGGER.debug('ZK connection state: %s', state)
    if state == zkutils.states.KazooState.LOST:
        _LOGGER.info('ZK connection lost, stopping node.')
        _LOGGER.info('Terminating svscan in %s', tm_env.init_dir)
        supervisor.control_svscan(
            tm_env.init_dir,
            supervisor.SvscanControlAction.quit
        )
        # server_init should be terminated at this point but exit just in case.
        utils.sys_exit(-1)


def _main_loop(tm_env, zkclient, zk_presence_path):
    """Main loop.

    Wait for zk event and check watchdogs.
    """
    down_reason = None
    # Now that the server is registered, setup the stop-on-delete
    # trigger and the deadman's trigger.
    node_deleted_event = zkclient.handler.event_object()
    node_deleted_event.clear()

    @zkclient.DataWatch(zk_presence_path)
    @utils.exit_on_unhandled
    def _exit_on_delete(data, _stat, event):
        """Force exit if server node is deleted."""
        if (data is None or
                (event is not None and event.type == 'DELETED')):
            # The node is deleted
            node_deleted_event.set()
            return False
        else:
            # Reestablish the watch.
            return True

    while not node_deleted_event.wait(_WATCHDOG_CHECK_INTERVAL):
        # NOTE: The loop time above is tailored to the kernel watchdog time.
        #       Be very careful before changing it.
        # Check our watchdogs
        result = tm_env.watchdogs.check()
        if result:
            # Something is wrong with the node, shut it down
            down_reason = 'watchdogs %r failed.' % result
            break

    return down_reason
