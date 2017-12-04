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

import logging
import os
import time

import click
import kazoo

from treadmill import appenv
from treadmill import context
from treadmill import netdev
from treadmill import postmortem
from treadmill import presence
from treadmill import supervisor
from treadmill import sysinfo
from treadmill import utils
from treadmill import zknamespace as z
from treadmill import zkutils


_LOGGER = logging.getLogger(__name__)


_WATCHDOG_CHECK_INTERVAL = 30
_KERNEL_WATCHDOG = None


def init():
    """Top level command handler."""
    @click.command()
    @click.option('--exit-on-fail', is_flag=True, default=False)
    @click.option('--zkid', help='Zookeeper session ID file.')
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('--runtime', envvar='TREADMILL_RUNTIME', required=True)
    def top(exit_on_fail, zkid, approot, runtime):
        """Run treadmill init process."""
        _LOGGER.info('Initializing Treadmill: %s (%s)', approot, runtime)

        tm_env = appenv.AppEnvironment(approot)
        zkclient = zkutils.connect(context.GLOBAL.zk.url,
                                   idpath=zkid,
                                   listener=_exit_clear_watchdog_on_lost)

        while not zkclient.exists(z.SERVER_PRESENCE):
            _LOGGER.warning('namespace not ready.')
            time.sleep(30)

        hostname = sysinfo.hostname()

        zk_server_path = z.path.server(hostname)
        zk_blackout_path = z.path.blackedout_server(hostname)
        zk_presence_path = None

        while not zkclient.exists(zk_server_path):
            _LOGGER.warning('server %s not defined in the cell.', hostname)
            time.sleep(30)

        _LOGGER.info('Checking blackout list.')
        blacklisted = bool(zkclient.exists(zk_blackout_path))

        if not blacklisted:
            # Node startup.
            zk_presence_path = _node_start(tm_env, runtime, zkclient, hostname)

            utils.report_ready()
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
                    acl=[zkutils.make_host_acl(hostname, 'rwcda')],
                    data=down_reason
                )
                trigger_postmortem = True
            else:
                # Blacked out manually
                trigger_postmortem = bool(zkclient.exists(zk_blackout_path))

            if trigger_postmortem:
                postmortem.run(approot)

        else:
            # Node was already blacked out.
            _LOGGER.warning('Shutting down blacked out node.')

        # This is the shutdown phase.

        # Delete the node
        if zk_presence_path:
            zkutils.ensure_deleted(zkclient, zk_presence_path)
        zkclient.remove_listener(_exit_clear_watchdog_on_lost)
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


def _node_start(tm_env, runtime, zkclient, hostname):
    """Node startup. Try to re-establish old session or start fresh.
    """
    old_session_ok = False
    old_presence_path = presence.find_server(zkclient, hostname)
    if old_presence_path:
        try:
            _data, metadata = zkclient.get(old_presence_path)
            if metadata.owner_session_id == zkclient.client_id[0]:
                _LOGGER.info('Reconnecting with previous session: %s',
                             metadata.owner_session_id)
                old_session_ok = True
            else:
                _LOGGER.info('Session id does not match, new session.')
                zkclient.delete(old_presence_path)
        except kazoo.client.NoNodeError:
            _LOGGER.info('%s does not exist.', old_presence_path)

    if old_session_ok:
        return old_presence_path
    return _node_initialize(tm_env, runtime, zkclient, hostname)


def _node_initialize(tm_env, runtime, zkclient, hostname):
    """Node initialization. Should only be done on a cold start.
    """
    try:
        node_info = sysinfo.node_info(tm_env, runtime)
        node_presence_path = presence.register_server(
            zkclient, hostname, node_info
        )

        # Invoke the local node initialization
        tm_env.initialize(node_info)
        return node_presence_path

    except Exception:  # pylint: disable=W0703
        _LOGGER.exception('Node initialization failed')
        zkclient.stop()


def _exit_clear_watchdog_on_lost(state):
    _LOGGER.debug('ZK connection state: %s', state)
    if state == zkutils.states.KazooState.LOST:
        _LOGGER.info('Exiting on ZK connection lost.')
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
