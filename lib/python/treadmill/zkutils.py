"""Treadmill ZooKeeper helper functions.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import fnmatch
import io
import logging
import os
import pickle
import sys
import urllib

import kazoo
import kazoo.client
import kazoo.exceptions
import kazoo.security
from kazoo.protocol import states
import six

from treadmill import plugin_manager
from treadmill import utils
from treadmill import sysinfo
from treadmill import yamlwrapper as yaml
from treadmill import zknamespace as z


_LOGGER = logging.getLogger(__name__)

logging.getLogger('kazoo.client').setLevel(logging.WARNING)

# This is the maximum time the start will try to connect for, i.e. 30 sec
ZK_MAX_CONNECTION_START_TIMEOUT = 30

DEFAULT_ACL = True


def _is_valid_perm(perm):
    """Check string to be valid permission spec."""
    for char in perm:
        if char not in 'rwcda':
            return False
    return True


def _make_anonymous_acl(perm):
    """Constructs anonymous (world) acl."""
    if not perm:
        perm = 'r'

    assert _is_valid_perm(perm)
    return kazoo.security.make_acl(
        'world', 'anyone',
        read='r' in perm,
        write='w' in perm,
        create='c' in perm,
        delete='d' in perm,
        admin='a' in perm
    )


class ZkClient(kazoo.client.KazooClient):
    """Default ZkClient."""

    def create(self, path, value=None, acl=None, ephemeral=False,
               sequence=False, makepath=False):
        """Safe wrapper around kazoo.client.create"""
        if value is None:
            value = ''
        return super().create(
            path,
            value=value,
            acl=self.make_default_acl(acl),
            ephemeral=ephemeral,
            sequence=sequence,
            makepath=makepath
        )

    def ensure_path(self, path, acl=None):
        """Safe wrapper around kazoo.client.ensure_path"""
        return super().ensure_path(path, acl=self.make_default_acl(acl))

    def set_acls(self, path, acls, version=-1):
        """Safe wrapper around kazoo.client.set_acls"""
        return super().set_acls(
            path,
            self.make_default_acl(acls),
            version=version
        )

    def make_anonymous_acl(self, perm):
        """Constructs anonymous acl."""
        assert _is_valid_perm(perm)
        return _make_anonymous_acl(perm)

    def make_user_acl(self, user, perm):
        """Constructs an ACL based on user and permissions."""
        assert _is_valid_perm(perm)
        del user
        return _make_anonymous_acl(perm)

    def make_host_acl(self, host, perm):
        """Constructs an ACL based on user and permissions."""
        assert _is_valid_perm(perm)
        del host
        return _make_anonymous_acl(perm)

    def make_role_acl(self, role, perm):
        """Constructs a file based acl based on role.
        """
        assert _is_valid_perm(perm)
        del role
        return _make_anonymous_acl(perm)

    def make_self_acl(self, perm):
        """Constucts acl for the current user.

        If the user is root, use host principal.
        """
        assert _is_valid_perm(perm)
        if utils.is_root():
            return self.make_host_acl(sysinfo.hostname(), perm)

        user = utils.get_current_username()
        return self.make_user_acl(user, perm)

    def make_default_acl(self, acls):
        """Constructs a default Treadmill acl."""
        if not DEFAULT_ACL:
            return acls

        realacl = [
            self.make_role_acl('readers', 'r'),
            self.make_role_acl('admin', 'rwcda'),
            self.make_self_acl('rwcda'),
        ]
        if acls:
            realacl.extend(acls)
        return realacl

    def make_servers_acl(self):
        """Make servers acl."""
        return self.make_role_acl('servers', 'rwcda')

    def make_servers_del_acl(self):
        """Make acl that allow servers role to delete only."""
        return self.make_role_acl('servers', 'd')


def exit_on_lost(state):
    """Watch for connection events and exit if disconnected."""
    _LOGGER.debug('ZK connection state: %s', state)
    if state == states.KazooState.LOST:
        _LOGGER.info('Exiting on ZK connection lost.')
        utils.sys_exit(-1)


def exit_on_disconnect(state):
    """Watch for connection events and exit if disconnected."""
    _LOGGER.debug('ZK connection state: %s', state)
    if state != states.KazooState.CONNECTED:
        _LOGGER.info('Exiting on ZK connection lost.')
        utils.sys_exit(-1)


def exit_never(state):
    """Watch for connection state, never exit."""
    _LOGGER.debug('ZK connection state: %s', state)


def disconnect(zkclient):
    """Gracefully close Zookeeper connection."""
    _LOGGER.info('Closing zk connection.')
    zkclient.stop()
    zkclient.close()


def connect(zkurl, idpath=None, listener=None, max_tries=30,
            timeout=ZK_MAX_CONNECTION_START_TIMEOUT, chroot=None,
            **connargs):
    """Establish connection with Zk and return KazooClient.

    :param max_tries:
        the maximum number of retries when trying to connect to the the
        servers; default is 10.

    :param timeout:
        the maximum timeout while trying to connect, that wait this much time
        while try to keep connecting.

    """
    client_id = None
    if idpath:
        if os.path.exists(idpath):
            with io.open(idpath, 'rb') as idfile:
                client_id = pickle.load(idfile)

    zkclient = connect_native(
        zkurl,
        client_id=client_id,
        listener=listener,
        timeout=timeout, max_tries=max_tries,
        chroot=chroot,
        **connargs
    )

    if idpath:
        client_id = zkclient.client_id
        with io.open(idpath, 'wb') as idfile:
            pickle.dump(client_id, idfile)

    return zkclient


def connect_native(zkurl, client_id=None, listener=None, max_tries=30,
                   timeout=ZK_MAX_CONNECTION_START_TIMEOUT, chroot=None,
                   **connargs):
    """Establish connection with Zk and return KazooClient.
    """
    _LOGGER.debug('Connecting to %s', zkurl)
    parsed = urllib.parse.urlparse(zkurl)

    # Load handler for the scheme. Special handling of "zookeeper" scheme,
    # allow default if it not specified in the entry points.
    try:
        zkclient_cls = plugin_manager.load(
            'treadmill.zookeeper.client',
            str(parsed.scheme)
        )
    except KeyError:
        _LOGGER.debug('Unable to load scheme: %s', parsed.scheme)
        if parsed.scheme == 'zookeeper':
            zkclient_cls = ZkClient
        else:
            _LOGGER.critical(
                'Unable to load zkclient for scheme: %s', parsed.scheme
            )
            raise

    hosts = parsed.netloc
    chroot = parsed.path

    zk_retry = {
        'delay': 0.2,
        'backoff': 2,
        'max_jitter': 0.2,
        'max_delay': 1,
        'max_tries': max_tries,
        'ignore_expire': False,
    }
    connargs.update({
        'client_id': client_id,
        'auth_data': [],
        'connection_retry': zk_retry,
        'command_retry': zk_retry,
        'hosts': hosts,
    })

    _LOGGER.debug(
        'Connecting to zookeeper: [%s:%s]: %r',
        zkclient_cls.__module__,
        zkclient_cls.__name__,
        connargs
    )
    zkclient = zkclient_cls(**connargs)
    if listener is None:
        listener = exit_on_disconnect

    zkclient.add_listener(listener)

    # This will CLOSE the connection and throw a time-out exception after
    # trying max_tries
    zkclient.start(timeout=timeout)
    if chroot:
        acl = zkclient.make_default_acl(None)
        path = []
        chroot_components = chroot.split('/')
        while chroot_components:
            path.append(chroot_components.pop(0))
            if len(path) > 1:
                component = '/'.join(path)
                if not zkclient.exists(component):
                    # TODO: need to compare acls if component exists.
                    try:
                        zkclient.create(component, b'', makepath=True, acl=acl)
                    except kazoo.exceptions.KazooException:
                        _LOGGER.exception('chroot %s does not exist.', chroot)
                        raise

        zkclient.chroot = chroot

    return zkclient


class SequenceNodeWatch:
    """Sequential nodes watcher which keeps track of last node seen."""

    def __init__(self, zkclient, func, delim, pattern, include_data):
        self.zkclient = zkclient
        self.func = func
        self.last = None
        self.delim = delim
        self.pattern = pattern
        self.include_data = include_data

    def nodes(self, children):
        """Yield previously unseen node."""
        if self.pattern:
            children = [node for node in children
                        if node.startswith(self.pattern)]

        seq_children = [(node[node.rfind(self.delim) + 1:], node)
                        for node in children if node.rfind(self.delim) > 0]

        # Sort nodes by seq #
        for seq, node in sorted(seq_children):
            if self.last is None or seq > self.last:
                self.last = seq
                yield node

    def invoke_callback(self, path, node):
        """Invokes callback for each new node."""
        try:
            fullpath = z.join_zookeeper_path(path, node)
            data = None
            stat = None
            if self.include_data:
                data, stat = self.zkclient.get(fullpath)
            self.func(fullpath, data, stat)
        except Exception:  # pylint: disable=W0703
            _LOGGER.critical('Unexpected error: %s', sys.exc_info()[0])

    def on_child(self, event):
        """The watch function."""
        if event.type == 'CHILD':
            children = self.zkclient.get_children(event.path, self.on_child)
            for node in self.nodes(children):
                self.invoke_callback(event.path, node)


def watch_sequence(zkclient, path, func, delim='-', pattern=None,
                   include_data=False):
    """Watch sequential nodes under path, invoke function with new nodes.

    When started, will invoke callback func with the list of sequence nodes,
    remembering the last node.

    For each node added, callback will be invoked only with newly added nodes.

    Delimiter is used to identify the sequence number of the node name, which
    can be anything. Optionally will filter nodes to start with given patter.
    """
    watcher = SequenceNodeWatch(zkclient, func, delim, pattern, include_data)

    def on_create(event):
        """Callback invoked when node is created."""
        assert event.path == path
        children = zkclient.get_children(path, watcher.on_child)
        for node in watcher.nodes(children):
            watcher.invoke_callback(path, node)

    if zkclient.exists(path, on_create):
        children = zkclient.get_children(path, watcher.on_child)
        for node in watcher.nodes(children):
            watcher.invoke_callback(path, node)


def _payload(data):
    """Converts payload to serialized bytes.
    """
    payload = b''
    if data is not None:
        if isinstance(data, bytes):
            payload = data
        elif isinstance(data, six.string_types) and hasattr(data, 'encode'):
            payload = data.encode()
        else:
            payload = yaml.dump(data).encode()
    return payload


def create(zkclient, path, data=None, acl=None, sequence=False,
           default_acl=True, ephemeral=False):
    """Serialize data into Zk node, fail if node exists."""
    payload = _payload(data)
    if default_acl:
        realacl = zkclient.make_default_acl(acl)
    else:
        realacl = acl

    return zkclient.create(path, payload, makepath=True, acl=realacl,
                           sequence=sequence, ephemeral=ephemeral)


def put(zkclient, path, data=None, acl=None, sequence=False, default_acl=True,
        ephemeral=False, check_content=False):
    """Serialize data into Zk node, converting data to YAML.

    Default acl is set to admin:all, anonymous:readonly. These acls are
    appended to any addidional acls provided in the argument.
    """
    payload = _payload(data)

    # Default acl assumes world readable data, safe to log the payload. If
    # default acl is not specified, do not log the payload as it may be
    # private.
    if default_acl:
        realacl = zkclient.make_default_acl(acl)
        _LOGGER.debug('put (default_acl=%s): %s acl=%s seq=%s', default_acl,
                      path, realacl, sequence)
    else:
        realacl = acl
        _LOGGER.debug('put %s *** acl=%s seq=%s', path, realacl, sequence)

    try:
        return zkclient.create(path, payload, makepath=True, acl=realacl,
                               sequence=sequence, ephemeral=ephemeral)
    except kazoo.client.NodeExistsError:
        # This will never happen for sequence node, so requestor knows the
        # path.
        #
        # If there is not change, return None to indicate update was not done.
        if check_content:
            current, _metadata = zkclient.get(path)
            if current == payload:
                _LOGGER.debug('%s is up to date', path)
                return None

        zkclient.set(path, payload)
        _LOGGER.debug('Setting ACL on %s to %r', path, realacl)
        zkclient.set_acls(path, realacl)
        return path


def update(zkclient, path, data, check_content=False):
    """Set data into Zk node, converting data to YAML."""
    _LOGGER.debug('update %s', path)

    payload = _payload(data)
    if check_content:
        current, _metadata = zkclient.get(path)
        if current == payload:
            return None

    zkclient.set(path, payload)
    return path


def get(zkclient, path, watcher=None, strict=True):
    """Read content of Zookeeper node and return YAML parsed object."""
    data, _metadata = get_with_metadata(zkclient, path, watcher=watcher,
                                        strict=strict)
    return data


def get_with_metadata(zkclient, path, watcher=None, strict=True):
    """Read content of Zookeeper node and return YAML parsed object."""
    data, metadata = zkclient.get(path, watch=watcher)

    result = None
    if data is not None:
        try:
            result = yaml.load(data)
        except yaml.YAMLError:
            if strict:
                raise
            else:
                result = data

    return result, metadata


def get_default(zkclient, path, watcher=None, strict=True, default=None):
    """Read content of Zookeeper node, return default value if does not exist.
    """
    try:
        return get(zkclient, path, watcher=watcher, strict=strict)
    except kazoo.client.NoNodeError:
        return default


def get_children_count(zkclient, path, exc_safe=True):
    """Gets the node children count."""
    try:
        _data, metadata = zkclient.get(path)
        return metadata.children_count
    except kazoo.client.NoNodeError:
        if exc_safe:
            return 0
        else:
            raise


def ensure_exists(zkclient, path, acl=None, sequence=False, data=None):
    """Creates path with correct ACL if path does not exist.

    If the path does not exist, creates the path with proper acl.

    If the path already exists, does not touch the content, but makes sure the
    acl is correct.
    """
    realacl = zkclient.make_default_acl(acl)
    try:
        # new node has default empty data
        newdata = _payload(data)
        return zkclient.create(path, newdata, makepath=True, acl=realacl,
                               sequence=sequence)
    except kazoo.client.NodeExistsError:
        # if data not provided, we keep original data pristine
        if data is not None:
            newdata = _payload(data)
            zkclient.set(path, newdata)

        zkclient.set_acls(path, realacl)
        return path


def ensure_deleted(zkclient, path, recursive=True):
    """Deletes the node if it exists."""
    try:
        _LOGGER.debug('Deleting %s', path)
        if recursive:
            for child in zkclient.get_children(path):
                ensure_deleted(zkclient, z.join_zookeeper_path(path, child))

        zkclient.delete(path)
    except kazoo.client.NoNodeError:
        _LOGGER.debug('Node %s does not exist.', path)


def exists(zk_client, zk_path, timeout=60):
    """wrapping the zk exists function with timeout"""
    node_created_event = zk_client.handler.event_object()

    def node_watch(event):
        """watch for node creation"""
        if event.type == kazoo.protocol.states.EventType.CREATED:
            node_created_event.set()

    if not zk_client.exists(zk_path, watch=node_watch):
        return node_created_event.wait(timeout)
    return True


def list_match(zkclient, path, pattern, watcher=None):
    """Get a list of nodes matching pattern."""
    children = zkclient.get_children(path, watch=watcher)

    return [node for node in children if fnmatch.fnmatch(node, pattern)]


def wait(zk_client, zk_path, wait_exists, timeout=None):
    """Wait for node to be in a given state."""
    node_created_event = zk_client.handler.event_object()

    def node_watch(event):
        """watch for node events."""
        _LOGGER.debug('Got event: %r', event)
        created = (event.type == kazoo.protocol.states.EventType.CREATED)
        deleted = (event.type == kazoo.protocol.states.EventType.DELETED)
        if (wait_exists and created) or (not wait_exists and deleted):
            node_created_event.set()

    if wait_exists == bool(zk_client.exists(zk_path, watch=node_watch)):
        return True
    else:
        _LOGGER.debug('Will wait for timeout: %r', timeout)
        return node_created_event.wait(timeout)


def with_retry(func, *args, **kwargs):
    """Calls function with retry."""
    zk_retry = kazoo.retry.KazooRetry(ignore_expire=False, max_tries=5)
    return zk_retry(func, *args, **kwargs)


def make_lock(zkclient, path):
    """Make lock."""
    _LOGGER.debug('Creating lock on: %s', path)
    zkclient.ensure_path(path)
    zkclient.add_listener(exit_on_disconnect)
    me = '%s.%d' % (sysinfo.hostname(), os.getpid())
    return zkclient.Lock(path, me)
