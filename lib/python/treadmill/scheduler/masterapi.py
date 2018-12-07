"""Treadmill master low level API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import kazoo
import six

from treadmill import trace
from treadmill import zknamespace as z
from treadmill import zkutils

from treadmill.trace.app import events as app_events

_LOGGER = logging.getLogger(__name__)


def _app_node(app_id, existing=True):
    """Returns node path given app id."""
    path = os.path.join(z.SCHEDULED, app_id)
    if not existing:
        path = path + '#'
    return path


def create_event(zkclient, priority, event, payload):
    """Places event on the event queue."""
    assert 0 <= priority <= 100
    node_path = z.path.event(
        '%(priority)03d-%(event)s-' % {'priority': priority, 'event': event})

    return os.path.basename(
        zkutils.put(
            zkclient,
            node_path,
            payload,
            acl=[zkclient.make_servers_acl()],
            sequence=True
        )
    )


def create_apps(zkclient, app_id, app, count, created_by=None):
    """Schedules new apps."""
    instance_ids = []
    acl = zkclient.make_servers_acl()
    for _idx in range(0, count):
        node_path = zkutils.put(zkclient,
                                _app_node(app_id, existing=False),
                                app,
                                sequence=True,
                                acl=[acl])
        instance_id = os.path.basename(node_path)
        instance_ids.append(instance_id)

        trace.post_zk(
            zkclient,
            app_events.PendingTraceEvent(
                instanceid=instance_id,
                why='%s:created' % created_by if created_by else 'created',
                payload=''
            )
        )

    return instance_ids


def delete_apps(zkclient, app_ids, deleted_by=None):
    """Unschedules apps."""
    for app_id in app_ids:
        zkutils.ensure_deleted(zkclient, _app_node(app_id))

        trace.post_zk(
            zkclient,
            app_events.PendingDeleteTraceEvent(
                instanceid=app_id,
                why='%s:deleted' % deleted_by if deleted_by else 'deleted'
            )
        )


def get_app(zkclient, app_id):
    """Return scheduled app details by app_id."""
    return zkutils.get_default(zkclient, _app_node(app_id))


def list_scheduled_apps(zkclient):
    """List all scheduled apps."""
    scheduled = zkclient.get_children(z.SCHEDULED)
    return scheduled


def list_running_apps(zkclient):
    """List all scheduled apps."""
    running = zkclient.get_children(z.RUNNING)
    return running


def update_app_priorities(zkclient, updates):
    """Updates app priority."""
    modified = []
    for app_id, priority in six.iteritems(updates):
        assert 0 <= priority <= 100

        app = get_app(zkclient, app_id)
        if app is None:
            # app does not exist.
            continue

        app['priority'] = priority

        if zkutils.update(zkclient, _app_node(app_id), app,
                          check_content=True):
            modified.append(app_id)

    if modified:
        create_event(zkclient, 1, 'apps', modified)


def create_bucket(zkclient, bucket_id, parent_id, traits=0):
    """Creates bucket definition in Zookeeper."""
    data = {
        'traits': traits,
        'parent': parent_id
    }
    if zkutils.put(zkclient,
                   z.path.bucket(bucket_id),
                   data,
                   check_content=True):
        create_event(zkclient, 0, 'buckets', None)


def update_bucket_traits(zkclient, bucket_id, traits):
    """Updates bucket traits."""
    data = get_bucket(zkclient, bucket_id)
    data['traits'] = traits
    zkutils.put(zkclient, z.path.bucket(bucket_id), data, check_content=True)


def get_bucket(zkclient, bucket_id):
    """Return bucket definition in Zookeeper."""
    return zkutils.get(zkclient, z.path.bucket(bucket_id))


def delete_bucket(zkclient, bucket_id):
    """Deletes bucket definition from Zoookeeper."""
    zkutils.ensure_deleted(zkclient, z.path.bucket(bucket_id))
    # NOTE: we never remove buckets, no need for event.


def list_buckets(zkclient):
    """List all buckets."""
    return sorted(zkclient.get_children(z.BUCKETS))


def create_server(zkclient, server_id, parent_id, partition):
    """Creates server definition in Zookeeper."""
    server_node = z.path.server(server_id)
    server_acl = zkclient.make_host_acl(server_id, 'rwcd')

    zkutils.ensure_exists(zkclient, server_node, acl=[server_acl])

    data = zkutils.get(zkclient, server_node)
    if not data:
        data = {}
    data.update({
        'parent': parent_id,
        'partition': partition,
    })

    _LOGGER.info('Creating server node %s with data %r and ACL %r',
                 server_node, data, server_acl)
    if zkutils.put(zkclient, server_node, data,
                   acl=[server_acl], check_content=True):
        create_event(zkclient, 0, 'servers', [server_id])


def list_servers(zkclient):
    """List all servers."""
    return sorted(zkclient.get_children(z.SERVERS))


def update_server_attrs(zkclient, server_id, partition):
    """Updates server traits."""
    node = z.path.server(server_id)
    data = zkutils.get(zkclient, node)
    data['partition'] = partition

    if zkutils.update(zkclient, node, data, check_content=True):
        create_event(zkclient, 0, 'servers', [server_id])


def update_server_capacity(zkclient, server_id,
                           memory=None, cpu=None, disk=None):
    """Update server capacity."""
    node = z.path.server(server_id)
    data = zkutils.get(zkclient, node)
    if memory:
        data['memory'] = memory
    if cpu:
        data['cpu'] = cpu
    if disk:
        data['disk'] = disk

    if zkutils.update(zkclient, node, data, check_content=True):
        create_event(zkclient, 0, 'servers', [server_id])


def update_server_features(zkclient, server_id, features):
    """Updates server features."""
    node = z.path.server(server_id)
    data = zkutils.get(zkclient, node)
    data['features'] = features

    if zkutils.update(zkclient, node, data, check_content=True):
        create_event(zkclient, 0, 'servers', [server_id])


def update_server_parent(zkclient, server_id, parent_id):
    """Update server parent."""
    node = z.path.server(server_id)
    data = zkutils.get(zkclient, node)
    data['parent'] = parent_id

    if zkutils.update(zkclient, node, data, check_content=True):
        create_event(zkclient, 0, 'servers', [server_id])


def delete_server(zkclient, server_id):
    """Delete the server in Zookeeper."""
    zkutils.ensure_deleted(zkclient, z.path.server(server_id))
    zkutils.ensure_deleted(zkclient, z.path.placement(server_id))
    zkutils.ensure_deleted(zkclient, z.path.version(server_id))
    zkutils.ensure_deleted(zkclient, z.path.version_history(server_id))
    create_event(zkclient, 0, 'servers', [server_id])


def update_server_state(zkclient, server_id, state, apps=None):
    """Freeze server."""
    create_event(zkclient, 0, 'server_state', [server_id, state, apps])


def get_server(zkclient, server_id, placement=False):
    """Return server object."""
    data = zkutils.get_default(zkclient, z.path.server(server_id), {})
    if placement:
        placement_data = zkutils.get_default(
            zkclient,
            z.path.placement(server_id)
        )
        if placement_data:
            data.update(placement_data)

    return data


def reboot_server(zkclient, server_id):
    """Create server reboot event."""
    zkutils.ensure_exists(zkclient, z.path.reboot(server_id),
                          acl=[zkclient.make_servers_del_acl()])


def cell_insert_bucket(zkclient, bucket_id):
    """Add bucket to the cell."""
    if not zkclient.exists(z.path.cell(bucket_id)):
        zkutils.ensure_exists(zkclient, z.path.cell(bucket_id))
        create_event(zkclient, 0, 'cell', None)


def cell_remove_bucket(zkclient, bucket_id):
    """Remove bucket from the cell."""
    if zkclient.exists(z.path.cell(bucket_id)):
        zkutils.ensure_deleted(zkclient, z.path.cell(bucket_id))
        create_event(zkclient, 0, 'cell', None)


def cell_buckets(zkclient):
    """Return list of top level cell buckets."""
    return sorted(zkclient.get_children(z.CELL))


def appmonitors(zkclient):
    """Return list of app monitors ids."""
    return sorted(zkclient.get_children(z.path.appmonitor()))


def get_suspended_appmonitors(zkclient):
    """Return appmonitor suspension information."""
    # we avoid returning None
    return zkutils.get(zkclient, z.path.appmonitor()) or {}


def get_appmonitor(zkclient, monitor_id,
                   raise_notfound=False, suspended_monitors=None):
    """Return app monitor given id."""
    try:
        data = zkutils.get(zkclient, z.path.appmonitor(monitor_id))
        data['_id'] = monitor_id
        if suspended_monitors is None:
            suspended_monitors = get_suspended_appmonitors(zkclient)
        data['suspend_until'] = suspended_monitors.get(monitor_id)
        return data
    except kazoo.client.NoNodeError:
        _LOGGER.info('App monitor does not exist: %s', monitor_id)
        if raise_notfound:
            raise
        else:
            return None


def update_appmonitor(zkclient, monitor_id, count, policy=None):
    """Configures app monitor."""
    data = get_appmonitor(zkclient, monitor_id)
    if data is None:
        data = {}

    if count is not None:
        data['count'] = count
    if policy is not None:
        data['policy'] = policy

    node = z.path.appmonitor(monitor_id)
    zkutils.put(zkclient, node, data, check_content=True)

    # return data directly. As check_content=True, we believe data is correct
    data['_id'] = monitor_id
    return data


def delete_appmonitor(zkclient, monitor_id):
    """Deletes app monitor."""
    zkutils.ensure_deleted(zkclient, z.path.appmonitor(monitor_id))


def identity_groups(zkclient):
    """List all identity groups."""
    return sorted(zkclient.get_children(z.IDENTITY_GROUPS))


def get_identity_group(zkclient, ident_group_id):
    """Return app monitor given id."""
    data = zkutils.get(zkclient, z.path.identity_group(ident_group_id))
    data['_id'] = ident_group_id
    return data


def update_identity_group(zkclient, ident_group_id, count):
    """Updates identity group count."""
    node = z.path.identity_group(ident_group_id)
    data = {'count': count}
    if zkutils.put(zkclient,
                   node,
                   data,
                   check_content=True,
                   acl=[zkclient.make_servers_acl()]):
        create_event(zkclient, 0, 'identity_groups', [ident_group_id])


def delete_identity_group(zkclient, ident_group_id):
    """Delete identity group."""
    node = z.path.identity_group(ident_group_id)
    zkutils.ensure_deleted(zkclient, node)
    create_event(zkclient, 0, 'identity_groups', [ident_group_id])


def update_allocations(zkclient, allocations):
    """Updates identity group count."""
    if zkutils.put(zkclient,
                   z.path.allocation(),
                   allocations,
                   check_content=True):
        create_event(zkclient, 0, 'allocations', None)


def get_scheduled_stats(zkclient):
    """Return count of scheduled apps by proid."""
    return zkutils.get_default(zkclient, z.SCHEDULED_STATS, {})
