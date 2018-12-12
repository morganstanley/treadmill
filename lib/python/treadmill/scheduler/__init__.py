"""Treadmill hierarchical scheduler.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc
import collections
import datetime
import heapq
import itertools
import logging
import operator
import sys
import time

import enum

import numpy as np
import six

_LOGGER = logging.getLogger(__name__)

MAX_PRIORITY = 100
DEFAULT_RANK = 100
_UNPLACED_RANK = sys.maxsize

DIMENSION_COUNT = None

_MAX_UTILIZATION = float('inf')
_GLOBAL_ORDER_BASE = time.mktime((2014, 1, 1, 0, 0, 0, 0, 0, 0))

# 21 day
DEFAULT_SERVER_UPTIME = 21 * 24 * 60 * 60

# 1 day
MIN_SERVER_UPTIME = 1 * 24 * 60 * 60

# 7 days
DEFAULT_MAX_APP_LEASE = 7 * 24 * 60 * 60

# Default partition threshold
DEFAULT_THRESHOLD = 0.9

# pylint: disable=C0302,too-many-lines


def _bit_count(value):
    """Returns number of bits set.
    """
    count = 0
    while value:
        value &= value - 1
        count += 1
    return count


def zero_capacity():
    """Returns zero capacity vector.
    """
    assert DIMENSION_COUNT is not None, 'Dimension count not set.'
    return np.zeros(DIMENSION_COUNT)


def eps_capacity():
    """Returns eps capacity vector.
    """
    assert DIMENSION_COUNT is not None, 'Dimension count not set.'
    return np.array(
        [np.finfo(float).eps for _x in range(0, DIMENSION_COUNT)]
    )


def _global_order():
    """Use timestamp in nanoseconds, from Jan 1st 2014, to break tie in
    scheduling conflicts for apps of the same priority, in a FIFO fashion.
    """
    # Take the current EPOCH in nanosec
    global_order = int(time.time() * 1000000) - _GLOBAL_ORDER_BASE
    return global_order


def utilization(demand, allocated, available):
    """Calculates utilization score.
    """
    return np.max(np.subtract(demand, allocated) / available)


def _all(oper, left, right):
    """Short circuit all for ndarray.
    """
    return all(
        oper(ai, bi)
        for ai, bi in six.moves.zip(left, right)
    )


def _any(oper, left, right):
    """Short circuit any for ndarray.
    """
    return any(
        oper(ai, bi)
        for ai, bi in six.moves.zip(left, right)
    )


def _any_eq(left, right):
    """Short circuit any eq for ndarray.
    """
    return _any(operator.eq, left, right)


def _any_isclose(left, right):
    """Short circuit any isclose for ndarray.
    """
    return _any(np.isclose, left, right)


def _any_lt(left, right):
    """Short circuit any lt for ndarray.
    """
    return _any(operator.lt, left, right)


def _any_le(left, right):
    """Short circuit any le for ndarray.
    """
    return _any(operator.le, left, right)


def _any_gt(left, right):
    """Short circuit any gt for ndarray.
    """
    return _any(operator.gt, left, right)


def _any_ge(left, right):
    """Short circuit any ge for ndarray.
    """
    return _any(operator.ge, left, right)


def _all_eq(left, right):
    """Short circuit all eq for ndarray.
    """
    return _all(operator.eq, left, right)


def _all_isclose(left, right):
    """Short circuit all isclose for ndarray.
    """
    return _all(np.isclose, left, right)


def _all_lt(left, right):
    """Short circuit all lt for ndarray.
    """
    return _all(operator.lt, left, right)


def _all_le(left, right):
    """Short circuit all le for ndarray.
    """
    return _all(operator.le, left, right)


def _all_gt(left, right):
    """Short circuit all gt for ndarray.
    """
    return _all(operator.gt, left, right)


def _all_ge(left, right):
    """Short circuit all ge for ndarray.
    """
    return _all(operator.ge, left, right)


class IdentityGroup:
    """Identity group.
    """
    __slots__ = (
        'available',
        'count',
    )

    def __init__(self, count=0):
        self.count = count
        self.available = set(range(0, count))

    def acquire(self):
        """Return next available identity or None.
        """
        if self.available:
            return self.available.pop()
        else:
            return None

    def release(self, ident):
        """Mark identity as available.
        """
        if ident < self.count:
            self.available.add(ident)

    def adjust(self, count):
        """Adjust identities with new count.

        If count is larger, add additional identities to the set.
        If count is lower, remove identities that are no longer valid.

        All apps that have invalid identities will be adjusted in the
        schedule cycle.
        """
        if count >= self.count:
            self.available ^= set(six.moves.xrange(self.count, count))
        else:
            self.available -= set(six.moves.xrange(count, self.count))
        self.count = count


class State(enum.Enum):
    """Enumeration of node/server states.
    """

    # Ready to accept new applications.
    # TODO: Fix attribute name
    up = 'up'  # pylint: disable=invalid-name

    # Applications need to be migrated.
    down = 'down'

    # Existing applications can stay, but will not accept new.
    frozen = 'frozen'


class Affinity:
    """Model affinity and affinity limits.
    """
    __slots__ = (
        'name',
        'limits',
        'constraints',
    )

    def __init__(self, name, limits=None):
        self.name = name
        self.limits = collections.defaultdict(lambda: float('inf'))
        if limits:
            self.limits.update(limits)

        # freeze affinity shape constraints.
        self.constraints = tuple([self.name] + sorted(self.limits.values()))


class Application:
    """Application object.
    """

    __slots__ = (
        'global_order',
        'name',
        'demand',
        'affinity',
        'priority',
        'allocation',
        'data_retention_timeout',
        'server',
        'lease',
        'identity',
        'identity_group',
        'identity_group_ref',
        'schedule_once',
        'evicted',
        'placement_expiry',
        'renew',
        'unschedule',
        'final_rank',
        'final_util',
        'constraints',
        'blacklisted',
        '_traits',
    )

    def __init__(self, name, priority, demand, affinity,
                 affinity_limits=None,
                 data_retention_timeout=0,
                 lease=0,
                 identity_group=None,
                 identity=None,
                 traits=0,
                 schedule_once=False):

        self.global_order = _global_order()
        self.allocation = None
        self.server = None

        self.name = name
        self.affinity = Affinity(affinity, affinity_limits)
        self.priority = priority
        self.demand = np.array(demand, dtype=float)
        self.data_retention_timeout = data_retention_timeout
        self.lease = lease
        self.identity_group = identity_group
        self.identity = identity
        self.identity_group_ref = None
        self.schedule_once = schedule_once
        self.evicted = False
        self.unschedule = False
        self.placement_expiry = None
        self.renew = False
        self.blacklisted = False
        self._traits = traits

    def shape(self):
        """Return tuple of application (constraints, demand).

        Application shape is tuple of constraints that affect application
        placement. Currently this includes affinity constraints and app lease
        time.
        """
        constraints = (self.affinity.constraints + (self.lease,))
        if self.allocation:
            constraints += self.allocation.constraints

        return constraints, self.demand

    def acquire_identity(self):
        """Try to acquire identity if belong to the group.

        Returns True if successfull or if identity group is none.
        """
        if not self.identity_group_ref:
            return True

        if self.identity is None:
            self.identity = self.identity_group_ref.acquire()
            _LOGGER.info('Acquired identity: %s: %s - %s',
                         self.name, self.identity_group, self.identity)
        return self.identity is not None

    def release_identity(self):
        """Release app identity.
        """
        if self.identity_group_ref and self.identity is not None:
            self.identity_group_ref.release(self.identity)
            self.identity = None

    def force_set_identity(self, identity):
        """Force identity of the app.
        """
        if identity is not None:
            assert self.identity_group_ref
            self.identity = identity
            self.identity_group_ref.available.discard(identity)

    def has_identity(self):
        """Checks if app has identity if identity group is specified.
        """
        return self.identity_group_ref is None or self.identity is not None

    @property
    def traits(self):
        """The app traits are derived from allocation.
        """
        if self.allocation is None:
            return self._traits
        else:
            return self._traits | self.allocation.traits


@six.add_metaclass(abc.ABCMeta)
class Strategy:
    """Base class for all placement strategies.
    """

    @abc.abstractmethod
    def suggested_node(self):
        """Suggested node that should be tried first.
        """

    @abc.abstractmethod
    def next_node(self):
        """Next node to try, if previous suggestion was rejected.
        """


class SpreadStrategy(Strategy):
    """Spread strategy will suggest new node for each subsequent placement.
    """
    __slots__ = (
        'current_idx',
        'node',
    )

    def __init__(self, node):
        self.current_idx = 0
        self.node = node

    def suggested_node(self):
        """Suggest next node from the cycle.
        """
        for _ in six.moves.xrange(0, len(self.node.children)):
            if self.current_idx == len(self.node.children):
                self.current_idx = 0

            current = self.node.children[self.current_idx]
            self.current_idx += 1
            if current:
                return current
        # Not a single non-none node.
        return None

    def next_node(self):
        """Suggest next node from the cycle.
        """
        return self.suggested_node()


class PackStrategy(Strategy):
    """Pack strategy will suggest same node until it is full.
    """
    __slots__ = (
        'current_idx',
        'node',
    )

    def __init__(self, node):
        self.current_idx = 0
        self.node = node

    def suggested_node(self):
        """Suggest same node as previous placement.
        """
        for _ in six.moves.xrange(0, len(self.node.children)):
            if self.current_idx == len(self.node.children):
                self.current_idx = 0
            node = self.node.children[self.current_idx]
            if node:
                return node

        return None

    def next_node(self):
        """Suggest next node from the cycle.
        """
        self.current_idx += 1
        return self.suggested_node()


class TraitSet:
    """Hierarchical set of traits.
    """
    __slots__ = (
        'self_traits',
        'children_traits',
        'traits',
    )

    def __init__(self, traits=0):
        if not traits:
            traits = 0

        # Private traits.
        assert isinstance(traits, six.integer_types)
        self.self_traits = traits

        # Union of all children traits.
        self.children_traits = dict()

        self._recalculate()

    def _recalculate(self):
        """Calculate combined set of all traits.
        """
        self.traits = self.self_traits
        for trait in six.itervalues(self.children_traits):
            self.traits |= trait

    def has(self, traits):
        """Check if all traits are present.
        """
        return (self.traits & traits) == traits

    def add(self, child, traits):
        """Add a child with given traits.
        """
        # Update children traits.
        self.children_traits[child] = traits
        self._recalculate()

    def remove(self, child):
        """Remove child traits from the list.
        """
        if child in self.children_traits:
            del self.children_traits[child]
        self._recalculate()

    def is_same(self, other):
        """Compares own traits, ignore child.
        """
        return self.self_traits == other.self_traits


class AffinityCounter:
    """Manages affinity count.
    """
    __slots__ = (
        'affinity_counter',
    )

    def __init__(self):
        self.affinity_counter = collections.Counter()


class Node:
    """Abstract placement node.
    """

    __slots__ = (
        'name',
        'level',
        'free_capacity',
        'parent',
        'children',
        'children_by_name',
        'traits',
        'labels',
        'affinity_counters',
        'valid_until',
        '_state',
        '_state_since',
    )

    def __init__(self, name, traits, level, valid_until=0):
        self.name = name
        self.level = level
        self.free_capacity = zero_capacity()
        self.parent = None
        self.children = list()
        self.children_by_name = dict()
        self.traits = TraitSet(traits)
        self.labels = set()
        self.affinity_counters = collections.Counter()
        self.valid_until = valid_until
        self._state = State.up
        self._state_since = time.time()

    def empty(self):
        """Return true if there are no children.
        """
        return not bool(self.children_by_name)

    def children_iter(self):
        """Iterate over active children.
        """
        for child in self.children:
            if child:
                yield child

    def get_state(self):
        """Returns tuple of (state, since).
        """
        return self. _state, self._state_since

    def set_state(self, state, since):
        """Sets the state and time since.
        """
        if self._state is not state:
            self._state_since = since
        self._state = state
        _LOGGER.debug('state: %s - (%s, %s)',
                      self.name, self._state, self._state_since)

    @property
    def state(self):
        """Return current state.
        """
        return self._state

    @state.setter
    def state(self, new_state):
        """Set node state and records time.
        """
        self.set_state(new_state, time.time())

    def add_child_traits(self, node):
        """Recursively add child traits up.
        """
        self.traits.add(node.name, node.traits.traits)
        if self.parent:
            self.parent.remove_child_traits(self.name)
            self.parent.add_child_traits(self)

    def adjust_valid_until(self, child_valid_until):
        """Recursively adjust valid until time.
        """
        if child_valid_until:
            self.valid_until = max(self.valid_until, child_valid_until)
        else:
            if self.empty():
                self.valid_until = 0
            else:
                self.valid_until = max([node.valid_until
                                        for node in self.children_iter()])

        if self.parent:
            self.parent.adjust_valid_until(child_valid_until)

    def remove_child_traits(self, node_name):
        """Recursively remove child traits up.
        """
        self.traits.remove(node_name)
        if self.parent:
            self.parent.remove_child_traits(self.name)
            self.parent.add_child_traits(self)

    def reset_children(self):
        """Reset children to empty list.
        """
        for child in self.children_iter():
            child.parent = None
        self.children = list()
        self.children_by_name = dict()

    def add_node(self, node):
        """Add child node, set the traits and propagate traits up.
        """
        assert node.parent is None
        assert node.name not in self.children_by_name

        node.parent = self
        self.children.append(node)
        self.children_by_name[node.name] = node

        self.add_child_traits(node)
        self.increment_affinity(node.affinity_counters)
        self.add_labels(node.labels)
        self.adjust_valid_until(node.valid_until)

    def add_labels(self, labels):
        """Recursively add labels to self and parents.
        """
        self.labels.update(labels)
        if self.parent:
            self.parent.add_labels(self.labels)

    def remove_node(self, node):
        """Remove child node and adjust the traits.
        """
        assert node.name in self.children_by_name

        del self.children_by_name[node.name]
        for idx in six.moves.xrange(0, len(self.children)):
            if self.children[idx] == node:
                self.children[idx] = None

        self.remove_child_traits(node.name)
        self.decrement_affinity(node.affinity_counters)
        self.adjust_valid_until(None)

        node.parent = None
        return node

    def remove_node_by_name(self, nodename):
        """Removes node by name.
        """
        assert nodename in self.children_by_name
        return self.remove_node(self.children_by_name[nodename])

    def check_app_constraints(self, app):
        """Find app placement on the node.
        """
        if app.allocation is not None:
            if app.allocation.label not in self.labels:
                _LOGGER.info('Missing label: %s on %s', app.allocation.label,
                             self.name)
                return False

        if app.traits != 0 and not self.traits.has(app.traits):
            _LOGGER.info('Missing traits: %s on %s', app.traits, self.name)
            return False

        if not self.check_app_affinity_limit(app):
            return False

        if _any_gt(app.demand, self.free_capacity):
            _LOGGER.info('Not enough free capacity: %s', self.free_capacity)
            return False

        return True

    def check_app_affinity_limit(self, app):
        """Check app affinity limits
        """
        count = self.affinity_counters[app.affinity.name]
        limit = app.affinity.limits[self.level]
        return count < limit

    def put(self, _app):
        """Abstract method, should never be called.
        """
        raise Exception('Not implemented.')

    def size(self, label):
        """Returns total capacity of the children.
        """
        if self.empty() or label not in self.labels:
            return eps_capacity()

        return np.sum([
            n.size(label) for n in self.children_iter()], 0)

    def members(self):
        """Return set of all leaf node names.
        """
        names = dict()
        for node in self.children_iter():
            names.update(node.members())

        return names

    def increment_affinity(self, counters):
        """Increment affinity counters recursively.
        """
        self.affinity_counters.update(counters)
        if self.parent:
            self.parent.increment_affinity(counters)

    def decrement_affinity(self, counters):
        """Decrement affinity counters recursively.
        """
        self.affinity_counters.subtract(counters)
        if self.parent:
            self.parent.decrement_affinity(counters)


class Bucket(Node):
    """Collection of nodes/buckets.
    """

    __slots__ = (
        'affinity_strategies',
        'traits',
    )

    _default_strategy_t = SpreadStrategy

    def __init__(self, name, traits=0, level=None):
        super(Bucket, self).__init__(name, traits, level)
        self.affinity_strategies = dict()
        self.traits = TraitSet(traits)

    def set_affinity_strategy(self, affinity, strategy_t):
        """Initilaizes placement strategy for given affinity.
        """
        self.affinity_strategies[affinity] = strategy_t(self)

    def get_affinity_strategy(self, affinity):
        """Returns placement strategy for the affinity, defaults to spread.
        """
        if affinity not in self.affinity_strategies:
            self.set_affinity_strategy(affinity, Bucket._default_strategy_t)

        return self.affinity_strategies[affinity]

    def adjust_capacity_up(self, new_capacity):
        """Node can only increase capacity.
        """
        self.free_capacity = np.maximum(self.free_capacity, new_capacity)
        if self.parent:
            self.parent.adjust_capacity_up(self.free_capacity)

    def adjust_capacity_down(self, prev_capacity=None):
        """Called when capacity is decreased.
        """
        if self.empty():
            self.free_capacity = zero_capacity()
            if self.parent:
                self.parent.adjust_capacity_down()
        else:
            if prev_capacity is not None and _all_lt(prev_capacity,
                                                     self.free_capacity):
                return

            free_capacity = zero_capacity()
            for child_node in self.children_iter():
                if child_node.state is not State.up:
                    continue

                free_capacity = np.maximum(free_capacity,
                                           child_node.free_capacity)
            # If resulting free_capacity is less the previous, we need to
            # adjust the parent, otherwise, nothing needs to be done.
            prev_capacity = self.free_capacity.copy()
            if _any_lt(free_capacity, self.free_capacity):
                self.free_capacity = free_capacity
                if self.parent:
                    self.parent.adjust_capacity_down(prev_capacity)

    def add_node(self, node):
        """Adds node to the bucket.
        """
        super(Bucket, self).add_node(node)
        self.adjust_capacity_up(node.free_capacity)

    def remove_node(self, node):
        """Removes node from the bucket.
        """
        super(Bucket, self).remove_node(node)
        # if _any_isclose(self.free_capacity, node.free_capacity):
        self.adjust_capacity_down(node.free_capacity)

        return node

    def put(self, app):
        """Try to put app on one of the nodes that belong to the bucket.
        """
        # Check if it is feasible to put app on some node low in the
        # hierarchy
        _LOGGER.debug('bucket.put: %s => %s', app.name, self.name)

        if not self.check_app_constraints(app):
            return False

        strategy = self.get_affinity_strategy(app.affinity.name)
        node = strategy.suggested_node()
        if node is None:
            _LOGGER.debug('All nodes in the bucket deleted.')
            return False

        nodename0 = node.name
        first = True

        while True:
            # End of iteration.
            if not first and node.name == nodename0:
                _LOGGER.debug('Finished iterating on: %s.', self.name)
                break
            first = False

            _LOGGER.debug('Trying node: %s:', node.name)

            if node.state is not State.up:
                _LOGGER.debug('Node not up: %s, %s', node.name, node.state)
            else:
                if node.put(app):
                    return True

            node = strategy.next_node()

        return False


class Server(Node):
    """Server object, final app placement.
    """

    __slots__ = (
        'init_capacity',
        'apps',
        'up_since',
        'presence_id',
    )

    def __init__(self, name, capacity, up_since=0, valid_until=0,
                 traits=0, label=None, presence_id=None):
        super(Server, self).__init__(name, traits=traits, level='server',
                                     valid_until=valid_until)
        self.labels = set([label])
        self.init_capacity = np.array(capacity, dtype=float)
        self.free_capacity = self.init_capacity.copy()
        self.apps = dict()
        self.up_since = up_since
        self.presence_id = presence_id

    def __str__(self):
        return 'server: %s %s' % (self.name, self.init_capacity)

    def is_same(self, other):
        """Compares capacity and traits against another server.

        valid_until is ignored, as server comes up after reboot will have
        different valid_until value.
        """
        return (self.labels == other.labels and
                _all_eq(self.init_capacity, other.init_capacity) and
                self.traits.is_same(other.traits))

    def put(self, app):
        """Tries to put the app on the server.
        """
        assert app.name not in self.apps
        _LOGGER.debug('server.put: %s => %s', app.name, self.name)

        if not self.check_app_lifetime(app):
            return False

        if not self.check_app_constraints(app):
            return False

        prev_capacity = self.free_capacity.copy()
        self.free_capacity -= app.demand
        self.apps[app.name] = app

        self.increment_affinity([app.affinity.name])
        app.server = self.name
        if self.parent:
            self.parent.adjust_capacity_down(prev_capacity)

        if app.placement_expiry is None:
            app.placement_expiry = time.time() + app.lease
        return True

    def restore(self, app, placement_expiry=None):
        """Put app back on the server, ignore app lifetime.
        """
        _LOGGER.debug('server.restore: %s => %s (%s)',
                      app.name, self.name, placement_expiry)

        lease = app.lease
        # If not explicit
        if placement_expiry is None:
            placement_expiry = app.placement_expiry

        app.lease = 0
        rc = self.put(app)

        app.lease = lease
        app.placement_expiry = placement_expiry

        return rc

    def renew(self, app):
        """Try to extend the placement for app lease.
        """
        can_renew = self.check_app_lifetime(app)
        if can_renew:
            app.placement_expiry = time.time() + app.lease

        return can_renew

    def check_app_lifetime(self, app):
        """Check if the app lease fits until server is rebooted.
        """
        # app with 0 lease can be placed anywhere (ignore potentially
        # expired servers)
        if not app.lease:
            return True

        return time.time() + app.lease < self.valid_until

    def remove(self, app_name):
        """Removes app from the server.
        """
        assert app_name in self.apps
        app = self.apps[app_name]
        del self.apps[app_name]

        app.server = None
        app.evicted = True
        app.unschedule = False
        app.placement_expiry = None

        self.free_capacity += app.demand
        self.decrement_affinity([app.affinity.name])

        if self.parent:
            self.parent.adjust_capacity_up(self.free_capacity)

    def remove_all(self):
        """Remove all apps.
        """
        # iterate over copy of the keys, as we are removing them in the loop.
        for appname in list(self.apps):
            self.remove(appname)

    def size(self, label):
        """Return server capacity.
        """
        if label not in self.labels:
            return eps_capacity()
        return self.init_capacity

    def members(self):
        """Return set of all leaf node names.
        """
        return {self.name: self}

    def set_state(self, state, since):
        """Change host state.
        """
        if self.state is state:
            return

        super(Server, self).set_state(state, since)

        if state == State.up:
            if self.parent:
                self.parent.adjust_capacity_up(self.free_capacity)
        elif state in (State.down, State.frozen):
            if self.parent:
                self.parent.adjust_capacity_down(self.free_capacity)
        else:
            raise Exception('Invalid state: ' % state)


class Allocation:
    """Allocation manages queue of apps sharing same reserved capacity.

    In reality allocation is tied to grn via application proid.

    Applications within the allocation are organized by application priority.

    Allocations are ranked, and the rank is used to globally order applications
    from different allocations into global queue.

    Default allocation has rank 100. Defining allocation with lower rank will
    result in all it's applications to be evaluated first regardless of
    utilization. This is used to model "system" applications that should be
    always present regardless of utilization.

    Allocation queue can be capped with max_utilization parameter. If set, it
    will specify the max_utilization which will be considered for scheduling.
    """

    __slots__ = (
        'reserved',
        'rank',
        'rank_adjustment',
        'traits',
        'label',
        'max_utilization',
        'apps',
        'sub_allocations',
        'path',
        'constraints',
    )

    def __init__(self, reserved=None, rank=None, traits=None,
                 max_utilization=None, partition=None):
        self.set_reserved(reserved)

        self.rank = None
        self.rank_adjustment = 0
        self.traits = 0
        self.label = partition
        self.max_utilization = _MAX_UTILIZATION
        self.reserved = zero_capacity()

        self.set_max_utilization(max_utilization)
        self.set_traits(traits)
        self.update(reserved, rank, 0)
        self.apps = dict()
        self.sub_allocations = dict()
        self.path = []

        # Freeze shape constraintes.
        self.constraints = (self.label, self.traits,)

    @property
    def name(self):
        """Returns full allocation name.
        """
        return '/'.join(self.path)

    def set_reserved(self, reserved):
        """Update reserved capacity.
        """
        if reserved is None:
            self.reserved = zero_capacity()
        elif isinstance(reserved, int):
            assert reserved == 0
            self.reserved = zero_capacity()
        elif isinstance(reserved, float):
            assert reserved == 0.0
            self.reserved = zero_capacity()
        elif isinstance(reserved, list):
            assert len(reserved) == DIMENSION_COUNT
            self.reserved = np.array(reserved, dtype=float)
        elif isinstance(reserved, np.ndarray):
            self.reserved = reserved
        else:
            assert 'Unsupported type: %r' % type(reserved)

    def update(self, reserved, rank, rank_adjustment, max_utilization=None):
        """Updates allocation.
        """
        if rank is not None:
            self.rank = rank
        else:
            self.rank = DEFAULT_RANK
        if rank_adjustment is not None:
            self.rank_adjustment = rank_adjustment
        self.set_reserved(reserved)
        self.set_max_utilization(max_utilization)

    def set_max_utilization(self, max_utilization):
        """Sets max_utilization, accounting for default None value.
        """
        if max_utilization is not None:
            self.max_utilization = max_utilization
        else:
            self.max_utilization = _MAX_UTILIZATION

    def set_traits(self, traits):
        """Set traits, account for default None value.
        """
        if not traits:
            self.traits = 0
        else:
            self.traits = traits

    def add(self, app):
        """Add application to the allocation queue.

        Once added, the scheduler will make an attempt to place the app on one
        of the cell nodes.
        """
        # Check that there are no duplicate app names.
        if app.name in self.apps:
            _LOGGER.warning(
                'Duplicate app on alllocation queue: %s', app.name
            )
            return

        app.allocation = self
        self.apps[app.name] = app

    def remove(self, name):
        """Remove application from the allocation queue.
        """
        if name in self.apps:
            self.apps[name].allocation = None
            del self.apps[name]

    def priv_utilization_queue(self):
        """Returns tuples for sorted by global utilization.

        Apps in the queue are ordered by priority, insertion order.

        Adding or removing maintains invariant that apps utilization
        monotonically increases as well.

        Returns local prioritization queue in a tuple where first element is
        utilization ratio, so that this queue is suitable for merging into
        global priority queue.
        """
        def _app_key(app):
            """Compares apps by priority, state, global index
            """
            return (-app.priority, 0 if app.server else 1,
                    app.global_order, app.name)

        prio_queue = sorted(six.viewvalues(self.apps), key=_app_key)

        acc_demand = zero_capacity()
        available = self.reserved + np.finfo(float).eps
        util_before = utilization(acc_demand, self.reserved, available)

        for app in prio_queue:
            acc_demand = acc_demand + app.demand
            util_after = utilization(acc_demand, self.reserved, available)
            # Priority 0 apps are treated specially - utilization is set to
            # max float.
            #
            # This ensures that they are at the end of the all queues.
            if app.priority == 0:
                util_before = _MAX_UTILIZATION
                util_after = _MAX_UTILIZATION

            # All things equal, already scheduled applications have priority
            # over pending.
            pending = 0 if app.server else 1
            if util_after <= self.max_utilization - 1:
                rank = self.rank
                if util_before < 0:
                    rank -= self.rank_adjustment
            else:
                rank = _UNPLACED_RANK

            entry = (rank, util_before, util_after, pending, app.global_order,
                     app)

            util_before = util_after
            yield entry

    def utilization_queue(self, free_capacity, visitor=None):
        """Returns utilization queue including the sub-allocs.

        All app queues from self and sub-allocs are merged in standard order,
        and then utilization is recalculated based on total reserved capacity
        of this alloc and sub-allocs combined.

        The function maintains invariant that any app (self or inside sub-alloc
        with utilization < 1 will remain with utilzation < 1.
        """
        total_reserved = self.total_reserved()
        queues = [
            alloc.utilization_queue(free_capacity, visitor)
            for alloc in six.itervalues(self.sub_allocations)
        ]

        queues.append(self.priv_utilization_queue())

        acc_demand = zero_capacity()
        available = total_reserved + free_capacity + np.finfo(float).eps
        util_before = utilization(acc_demand, total_reserved, available)

        for item in heapq.merge(*queues):
            rank, _u_before, _u_after, pending, order, app = item
            acc_demand = acc_demand + app.demand
            util_after = utilization(acc_demand, total_reserved, available)
            if app.priority == 0:
                util_before = _MAX_UTILIZATION
                util_after = _MAX_UTILIZATION

            # - lower rank allocations take precedence.
            # - for same rank, utilization takes precedence
            # - False < True, so for apps with same utilization we prefer
            #   those that already running (False == not pending)
            # - Global order
            entry = (rank, util_before, util_after, pending, order, app)
            if visitor:
                visitor(self, entry, acc_demand)

            util_before = util_after
            yield entry

    def total_reserved(self):
        """Total reserved capacity including sub-allocs.
        """
        return six.moves.reduce(
            lambda acc, alloc: acc + alloc.total_reserved(),
            six.itervalues(self.sub_allocations),
            self.reserved
        )

    def add_sub_alloc(self, name, alloc):
        """Add child allocation.
        """
        self.sub_allocations[name] = alloc
        assert not alloc.path
        alloc.path = self.path + [name]
        alloc.label = self.label

    def remove_sub_alloc(self, name):
        """Remove chlid allocation.
        """
        if name in self.sub_allocations:
            del self.sub_allocations[name]

    def get_sub_alloc(self, name):
        """Return sub allocation, create empty if it does not exist.
        """
        if name not in self.sub_allocations:
            self.add_sub_alloc(name, Allocation())
        return self.sub_allocations[name]

    def all_apps(self):
        """Return all apps in allocation and sub-allocations."""
        all_apps = list(six.itervalues(self.apps))
        for alloc in six.itervalues(self.sub_allocations):
            all_apps.extend(alloc.all_apps())
        return all_apps


class Partition:
    """Cell partition.
    """

    __slots__ = (
        'allocation',
        'max_server_uptime',
        'max_lease',
        'threshold',
        'label',

        '_reboot_buckets',
        '_reboot_dates',
        '_reboot_last',
    )

    def __init__(self, max_server_uptime=None, max_lease=None, threshold=None,
                 label=None, reboot_schedule=None, now=None):
        self.label = label
        self.allocation = Allocation(partition=label)

        # Default -
        if not max_server_uptime:
            max_server_uptime = DEFAULT_SERVER_UPTIME
        if not max_lease:
            max_lease = DEFAULT_MAX_APP_LEASE
        if not threshold:
            threshold = DEFAULT_THRESHOLD

        self.max_server_uptime = max_server_uptime
        self.max_lease = max_lease
        self.threshold = threshold

        if not reboot_schedule:
            # reboot every day
            reboot_schedule = {day: (23, 59, 59) for day in range(7)}

        if not now:
            now = time.time()

        self._reboot_dates = reboot_dates(
            reboot_schedule,
            start_date=datetime.date.fromtimestamp(now)
        )
        self._reboot_buckets = []
        self._reboot_last = now

        self.tick(now)

    def _find_bucket(self, timestamp):
        """Try to find bucket with given timestamp.
        """
        for bucket in self._reboot_buckets:
            if bucket.timestamp == timestamp:
                return bucket

        return None

    def add(self, server, timestamp=None):
        """Add server.
        """
        bucket = None

        if timestamp:
            bucket = self._find_bucket(timestamp)

        # servers with larger than max lifetime should be rebooted at
        # the next opportunity
        if (self._reboot_buckets[0].timestamp >
                server.up_since + DEFAULT_SERVER_UPTIME):
            bucket = self._reboot_buckets[0]

        if not bucket:
            bucket = min(reversed(self._reboot_buckets),
                         key=lambda b: b.cost(server))

        bucket.add(server)

    def remove(self, server):
        """Remove server.
        """
        for bucket in self._reboot_buckets:
            bucket.remove(server)

    def tick(self, now):
        """Do per-tick-bookkeeping.
        """
        while self._reboot_last <= now + DEFAULT_SERVER_UPTIME:
            bucket = RebootBucket(next(self._reboot_dates))
            self._reboot_buckets.append(bucket)
            self._reboot_last = bucket.timestamp

        while self._reboot_buckets[0].timestamp < now:
            self._reboot_buckets.pop(0)


class PartitionDict(dict):
    """Dict that creates partitions on demand.

    We use this instead of collections.defaultdict so that we can provide
    the new partition with its label, to be propagated to its allocations.
    """
    def __missing__(self, label):
        """Create a new partition, passing the label to its constructor.
        """
        self[label] = Partition(label=label)
        return self[label]


# pylint: disable=invalid-name
def reboot_dates(schedule, start_date=None):
    """Generate list of valid reboot dates.
    """
    date = datetime.date.today()
    if start_date:
        date = start_date

    while True:

        weekday = date.weekday()
        if weekday in schedule:
            h, m, s = schedule[weekday]
            yield time.mktime((date.year, date.month, date.day,
                               h, m, s, 0, 0, 0))

        date += datetime.timedelta(days=1)


class RebootBucket:
    """Bucket of servers to be rebooted at the same time.
    """
    __slots__ = (
        'timestamp',
        'servers',
    )

    def __init__(self, timestamp):
        self.timestamp = timestamp
        self.servers = set()

    def add(self, server):
        """Add server to this bucket.
        """
        self.servers.add(server)
        server.valid_until = self.timestamp
        _LOGGER.info('Setting valid until on server: %s %s',
                     server.name, server.valid_until)

    def remove(self, server):
        """Remove server from this bucket.
        """
        try:
            self.servers.remove(server)
        except KeyError:
            pass

    def cost(self, server):
        """The cost of adding server to this bucket.
        """
        if self.timestamp > server.up_since + DEFAULT_SERVER_UPTIME:
            return float('inf')

        if self.timestamp < server.up_since + MIN_SERVER_UPTIME:
            return float('inf')

        return len(self.servers)


class PlacementFeasibilityTracker:
    """Tracks similar apps placement failures."""

    def __init__(self):
        self.recorder = dict()

    def feasible(self, app):
        """Checks if it is feasible to satisfy demand."""
        constraints, demand = app.shape()
        if constraints in self.recorder:
            # If demand is >= than recorded failure, placement is not feasible.
            if _all_ge(demand, self.recorder[constraints]):
                return False

        return True

    def adjust(self, app):
        """Adjust info about failed placement."""
        constraints, demand = app.shape()
        if constraints not in self.recorder:
            self.recorder[constraints] = demand
        else:
            if _all_le(demand, self.recorder[constraints]):
                self.recorder[constraints] = demand


class Cell(Bucket):
    """Top level node.
    """
    __slots__ = (
        'partitions',
        'next_event_at',
        'apps',
        'identity_groups',
    )

    def __init__(self, name):
        super(Cell, self).__init__(name, traits=0, level='cell')

        self.partitions = PartitionDict()
        self.apps = dict()
        self.identity_groups = collections.defaultdict(IdentityGroup)
        self.next_event_at = np.inf

    def add_app(self, allocation, app):
        """Adds application to the scheduled list.
        """
        assert allocation is not None

        if app.allocation:
            app.allocation.remove(app.name)
        allocation.add(app)
        self.apps[app.name] = app

        if app.identity_group:
            app.identity_group_ref = self.identity_groups[app.identity_group]

    def remove_app(self, appname):
        """Remove app from scheduled list.
        """
        if appname not in self.apps:
            return
        app = self.apps[appname]

        servers = self.members()
        if app.server in servers:
            servers[app.server].remove(app.name)
        if app.allocation:
            app.allocation.remove(app.name)

        app.release_identity()
        del self.apps[appname]

    def configure_identity_group(self, name, count):
        """Add identity group to the cell.
        """
        if name not in self.identity_groups:
            self.identity_groups[name] = IdentityGroup(count)
        else:
            self.identity_groups[name].adjust(count)

    def remove_identity_group(self, name):
        """Remove identity group.
        """
        ident_group = self.identity_groups.get(name)
        if ident_group:
            in_use = False
            for app in six.itervalues(self.apps):
                if app.identity_group_ref == ident_group:
                    ident_group.adjust(0)
                    in_use = True
                    break
            if not in_use:
                del self.identity_groups[name]

    def _fix_invalid_placements(self, queue, servers):
        """If app is placed on non-existent server, set server to None.
        """
        for app in queue:
            if app.server and app.server not in servers:
                app.server = None
                app.evicted = True
                app.release_identity()

    def _record_rank_and_util(self, queue):
        """Set final rank and utilization for all apps in the queue.
        """
        for item in queue:
            rank = item[0]
            util = item[1]
            app = item[-1]

            app.final_rank = rank
            app.final_util = util

    def _fix_invalid_identities(self, queue, servers):
        """Check that app identity is valid for given identity group.
        """
        for app in queue:
            if app.identity is not None and app.identity_group_ref is not None:
                # Can happen if identity group was adjusted to lower count.
                if app.identity >= app.identity_group_ref.count:
                    # Can't release identity as it is invalid.
                    _LOGGER.info('Identity exceeds limit: %s - %s, limit %s',
                                 app.name, app.identity,
                                 app.identity_group_ref.count)
                    app.identity = None
                    # Invalidate any existing placement.
                    if app.server:
                        servers[app.server].remove(app.name)

    def _handle_inactive_servers(self, servers):
        """Migrate apps from inactive servers.
        """
        self.next_event_at = np.inf
        for server in servers.values():
            state, since = server.get_state()
            to_be_moved = []

            if state == State.down:
                _LOGGER.debug('Server state is down: %s', server.name)
                for name, app in server.apps.items():
                    if app.data_retention_timeout is None:
                        expires_at = 0
                    else:
                        expires_at = since + app.data_retention_timeout

                    if expires_at <= time.time():
                        _LOGGER.debug('Expired placement: %s', name)
                        to_be_moved.append(app)
                    else:
                        _LOGGER.debug('Keep placement: %s until %s',
                                      name, expires_at)
                        self.next_event_at = min(expires_at,
                                                 self.next_event_at)
            elif state == State.frozen:
                _LOGGER.debug('Server state is frozen: %s', server.name)
                to_be_moved = [app for app in server.apps.values()
                               if app.unschedule]

            for app in to_be_moved:
                server.remove(app.name)
                app.release_identity()

    def _handle_blacklisted_apps(self, queue, servers):
        """Remove blacklisted apps from servers.
        """
        for app in queue:
            if app.blacklisted and app.server:
                server = servers[app.server]
                _LOGGER.info('Removing blacklisted app %s from %s',
                             app.name, server.name)
                server.remove(app.name)
                app.release_identity()

    def _find_placements(self, queue, servers):
        """Run the queue and find placements.
        """
        # TODO: refactor to get rid of warnings.
        #
        # pylint: disable=too-many-branches,too-many-statements
        #
        # At this point, if app.server is defined, it points to attached
        # server.
        evicted = dict()
        reversed_queue = queue[::-1]

        placement_tracker = PlacementFeasibilityTracker()

        for app in queue:
            _LOGGER.debug('scheduling %s', app.name)

            if app.blacklisted:
                _LOGGER.info('App %s is blacklisted', app.name)
                continue

            if app.final_rank == _UNPLACED_RANK:
                if app.server:
                    assert app.server in servers
                    assert app.has_identity()
                    servers[app.server].remove(app.name)
                    app.release_identity()

                continue

            restore = {}
            if app.renew:
                assert app.server
                assert app.has_identity()
                assert app.server in servers
                server = servers[app.server]
                if not server.renew(app):
                    # Save information that will be used to restore placement
                    # in case renewal fails.
                    _LOGGER.debug('Cannot renew app %s on server %s',
                                  app.name, app.server)
                    restore['server'] = server
                    restore['placement_expiry'] = app.placement_expiry
                    server.remove(app.name)

            # At this point app was either renewed on the same server, or
            # temporarily removed from server if renew failed.
            #
            # If placement will be found, renew should remain False. If
            # placement will not be found, renew will be set to True when
            # placement is restored to the server it was running.
            app.renew = False

            if app.server:
                assert app.server in servers
                assert app.has_identity()
                continue

            assert app.server is None

            if not app.acquire_identity():
                _LOGGER.info('Unable to acquire identity: %s, %s', app.name,
                             app.identity_group)
                continue

            # If app was evicted before, try to restore to the same node.
            if app in evicted:
                assert app.has_identity()

                evicted_from, app_expiry = evicted[app]
                del evicted[app]
                if evicted_from.restore(app, app_expiry):
                    app.evicted = False
                    continue

            assert app.server is None

            if app.schedule_once and app.evicted:
                continue

            # Check if placement is feasible.
            if not placement_tracker.feasible(app):
                _LOGGER.info(
                    'Placement not feasible: %s %r', app.name, app.shape()
                )
                continue

            if not self.put(app):
                # There is not enough capacity, from the end of the queue,
                # evict apps, freeing capacity.
                for evicted_app in reversed_queue:
                    # We reached the app we can't place
                    if evicted_app == app:
                        break

                    # The app is not yet placed, skip
                    if not evicted_app.server:
                        continue

                    assert evicted_app.server in servers
                    evicted_app_server = servers[evicted_app.server]

                    # Do not consider servers that are not up.
                    if evicted_app_server.state is not State.up:
                        continue

                    evicted[evicted_app] = (evicted_app_server,
                                            evicted_app.placement_expiry)
                    evicted_app_server.remove(evicted_app.name)

                    # TODO: we need to check affinity limit constraints on
                    #       each level, all the way to the top.
                    if evicted_app_server.put(app):
                        break

            # Placement failed.
            if not app.server:
                # If renewal attempt failed, restore previous placement and
                # expiry date.
                if restore:
                    restore['server'].restore(app, restore['placement_expiry'])
                    app.renew = True
                else:
                    app.release_identity()
                    placement_tracker.adjust(app)

    def schedule_alloc(self, allocation, servers):
        """Run the scheduler for given allocation.
        """
        begin = time.time()

        size = self.size(allocation.label)
        util_queue = list(allocation.utilization_queue(size))
        self._record_rank_and_util(util_queue)
        queue = [item[-1] for item in util_queue]

        self._find_placements(queue, servers)

        _LOGGER.info('Scheduled %s (%d) apps in %r',
                     allocation.label,
                     len(queue),
                     time.time() - begin)

    def schedule(self):
        """Run the scheduler.
        """
        begin = time.time()

        all_apps = []
        for label, partition in six.iteritems(self.partitions):
            allocation = partition.allocation
            all_apps.extend(allocation.all_apps())

        before = [(app.name, app.server, app.placement_expiry)
                  for app in all_apps]

        queue = self.apps.values()
        servers = self.members()
        self._fix_invalid_placements(queue, servers)
        self._handle_inactive_servers(servers)
        self._handle_blacklisted_apps(queue, servers)
        self._fix_invalid_identities(queue, servers)

        for label, partition in six.iteritems(self.partitions):
            allocation = partition.allocation
            allocation.label = label
            self.schedule_alloc(allocation, servers)

        after = [(app.server, app.placement_expiry)
                 for app in all_apps]

        placement = [
            tuple(itertools.chain(b, a))
            for b, a in six.moves.zip(before, after)
        ]

        for appname, s_before, exp_before, s_after, exp_after in placement:
            if s_before != s_after:
                _LOGGER.info('New placement: %s - %s => %s',
                             appname, s_before, s_after)
            else:
                if exp_before != exp_after:
                    _LOGGER.info('Renewed: %s [%s] - %s => %s',
                                 appname, s_before, exp_before, exp_after)

        _LOGGER.info('Total scheduler time for %s apps: %r (sec)',
                     len(all_apps),
                     time.time() - begin)
        return placement

    def resolve_reboot_conflicts(self):
        """Adjust server exipiration time to avoid conflicts.
        """


def dumps(cell):
    """Serializes cell to string.
    """
    del cell
    return ''


def loads(data):
    """Loads scheduler from string.
    """
    del data
    assert False, 'not implemented.'
