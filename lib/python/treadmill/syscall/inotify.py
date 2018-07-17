"""Linux inotify(7) API wrapper module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import logging
import operator
import os
import struct

import ctypes
from ctypes import (
    c_int,
    c_char_p,
    c_uint32,
)
from ctypes.util import find_library

import enum
import six

_LOGGER = logging.getLogger(__name__)


###############################################################################
# Map the C interface

_LIBC_PATH = find_library('c')
_LIBC = ctypes.CDLL(_LIBC_PATH, use_errno=True)

if any([getattr(_LIBC, func_name, None) is None
        for func_name in ['inotify_init1',
                          'inotify_add_watch',
                          'inotify_rm_watch']]):
    raise ImportError('Unsupported libc version found: %s' % _LIBC_PATH)


###############################################################################
# int inotify_init(void);
_INOTIFY_INIT1_DECL = ctypes.CFUNCTYPE(c_int, c_int, use_errno=True)
_INOTIFY_INIT1 = _INOTIFY_INIT1_DECL(('inotify_init1', _LIBC))


def inotify_init(flags=0):
    """Initializes a new inotify instance and returns a file descriptor
    associated with a new inotify event queue.

    :param ``INInitFlags`` flags:
        Optional flag to control the inotify_init behavior.
    """
    fileno = _INOTIFY_INIT1(flags)
    if fileno < 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno),
                      'inotify_init1(%r)' % flags)
    return fileno


###############################################################################
# Constants copied from sys/inotify.h
#
# See man inotify(7) for more details.
#
class INInitFlags(enum.IntEnum):
    """Flags supported by inotify_init(2).
    """

    NONBLOCK = 0o4000
    CLOEXEC = 0o2000000


#: Set the O_NONBLOCK file status flag on the new open file description.  Using
#: this flag saves extra calls to fcntl(2) to achieve the same result.
#: (since Linux 2.6.27)
IN_NONBLOCK = INInitFlags.NONBLOCK

#: Set the close-on-exec (FD_CLOEXEC) flag on the new file descriptor.  See the
#: description of the O_CLOEXEC flag in open(2) for reasons why this may be
#: useful.
#: (since Linux 2.6.27)
IN_CLOEXEC = INInitFlags.CLOEXEC


###############################################################################
# int inotify_add_watch(int fileno, const char *pathname, uint32_t mask);
_INOTIFY_ADD_WATCH_DECL = ctypes.CFUNCTYPE(c_int, c_int, c_char_p, c_uint32,
                                           use_errno=True)
_INOTIFY_ADD_WATCH = _INOTIFY_ADD_WATCH_DECL(('inotify_add_watch', _LIBC))


def inotify_add_watch(fileno, path, mask):
    """Add a watch to an initialized inotify instance.

    :params ``int`` fileno:
        Inotify socket.
    :params ``str`` path:
        Path to add the watch on.
    :params ``int`` mask:
        Mask of :class:`INAddWatchFlags` values controlling the watch creation.
    :returns:
        ``int`` - Corresponding watch ID.
    """
    encoded_path = path.encode()
    watch_id = _INOTIFY_ADD_WATCH(fileno, encoded_path, mask)
    if watch_id < 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno),
                      'inotify_add_watch(%r, %r, %r)' % (fileno, path, mask))
    return watch_id


###############################################################################
# Constants copied from sys/inotify.h
#
# See man inotify(7) for more details.
#
class INAddWatchFlags(enum.IntEnum):
    """Special flags for inotify_add_watch.
    """
    #: Do not follow a symbolic link.
    DONT_FOLLOW = 0x02000000
    #: Add to the mask of an existing watch.
    MASK_ADD = 0x20000000
    #: Only send event once.
    ONESHOT = 0x80000000
    #: Only watch the path if it's a directory.
    ONLYDIR = 0x01000000


#: Don't dereference pathname if it is a symbolic link.
#: (since Linux 2.6.15)
IN_DONT_FOLLOW = INAddWatchFlags.DONT_FOLLOW

#: Add (OR) events to watch mask for this pathname if it already exists
#: (instead of replacing mask).
IN_MASK_ADD = INAddWatchFlags.MASK_ADD

#: Monitor pathname for one event, then remove from watch list.
IN_ONESHOT = INAddWatchFlags.ONESHOT

#: Only watch pathname if it's a directory.
#: (since Linux 2.6.15)
IN_ONLYDIR = INAddWatchFlags.ONLYDIR


###############################################################################
# int inotify_rm_watch(int fileno, uint32_t wd);
_INOTIFY_RM_WATCH_DECL = ctypes.CFUNCTYPE(c_int, c_int, c_uint32,
                                          use_errno=True)
_INOTIFY_RM_WATCH = _INOTIFY_RM_WATCH_DECL(('inotify_rm_watch', _LIBC))


def inotify_rm_watch(fileno, watch_id):
    """Remove an existing watch from an inotify instance.

    :params ``int`` fileno:
        Inotify socket.
    :params ``int`` watch_id:
        Watch ID to remove.
    """
    res = _INOTIFY_RM_WATCH(fileno, watch_id)
    if res < 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno),
                      'inotify_rm_watch(%r, %r)' % (fileno, watch_id))


INOTIFY_EVENT_HDRSIZE = struct.calcsize('iIII')


###############################################################################
def _parse_buffer(event_buffer):
    """Parses an inotify event buffer of ``inotify_event`` structs read from
    the inotify socket.

    The inotify_event structure looks like this::

        struct inotify_event {
            __s32 wd;            /* watch descriptor */
            __u32 mask;          /* watch mask */
            __u32 cookie;        /* cookie to synchronize two events */
            __u32 len;           /* length (including nulls) of name */
            char  name[0];       /* stub for possible name */
        };

    The ``cookie`` member of this struct is used to pair two related
    events, for example, it pairs an IN_MOVED_FROM event with an
    IN_MOVED_TO event.
    """
    while len(event_buffer) >= INOTIFY_EVENT_HDRSIZE:
        wd, mask, cookie, length = struct.unpack_from('iIII', event_buffer, 0)
        name = event_buffer[
            INOTIFY_EVENT_HDRSIZE:
            INOTIFY_EVENT_HDRSIZE + length
        ]
        name = name.rstrip(b'\x00')
        event_buffer = event_buffer[INOTIFY_EVENT_HDRSIZE + length:]
        yield wd, mask, cookie, name

    assert not event_buffer, 'Unparsed bytes left in buffer: %r' % event_buffer


###############################################################################
# Constants copied from sys/inotify.h
#
# See man inotify(7) for more details.
#
# Constants related to inotify. See man inotify(7) and sys/inotify.h

class INEvent(enum.IntEnum):
    """Inotify events.
    """
    # Events triggered by user-space

    ACCESS = 0x00000001
    ATTRIB = 0x00000004
    CLOSE_WRITE = 0x00000008
    CLOSE_NOWRITE = 0x00000010
    CREATE = 0x00000100
    DELETE = 0x00000200
    DELETE_SELF = 0x00000400
    MODIFY = 0x00000002
    MOVE_SELF = 0x00000800
    MOVED_FROM = 0x00000040
    MOVED_TO = 0x00000080
    OPEN = 0x00000020

    # Events sent by the kernel

    IGNORED = 0x00008000
    ISDIR = 0x40000000
    Q_OVERFLOW = 0x00004000
    UNMOUNT = 0x00002000


#: File was accessed (read).
IN_ACCESS = INEvent.ACCESS
#: Metadata changed, e.g. permissions, timestamps, extended attributes, link
#: count (since Linux 2.6.25), UID, GID, etc.
IN_ATTRIB = INEvent.ATTRIB
#: File opened for writing was closed.
IN_CLOSE_WRITE = INEvent.CLOSE_WRITE
#: File not opened for writing was closed.
IN_CLOSE_NOWRITE = INEvent.CLOSE_NOWRITE
#: File/directory created in watched directory.
IN_CREATE = INEvent.CREATE
#: File/directory deleted from watched directory.
IN_DELETE = INEvent.DELETE
#: Watched file/directory was itself deleted.
IN_DELETE_SELF = INEvent.DELETE_SELF
#: File was modified.
IN_MODIFY = INEvent.MODIFY
#: Watched file/directory was itself moved.
IN_MOVE_SELF = INEvent.MOVE_SELF
#: File moved out of watched directory.
IN_MOVED_FROM = INEvent.MOVED_FROM
#: File moved into watched directory.
IN_MOVED_TO = INEvent.MOVED_TO
#: File was opened.
IN_OPEN = INEvent.OPEN

#: Watch was removed explicitly (inotify_rm_watch(2)) or automatically (file
#: was deleted, or file system was unmounted).
IN_IGNORED = INEvent.IGNORED
#: Subject of this event is a directory.
IN_ISDIR = INEvent.ISDIR
#: Event queue overflowed (wd is -1 for this event).
IN_Q_OVERFLOW = INEvent.Q_OVERFLOW
#: File system containing watched object was unmounted.
IN_UNMOUNT = INEvent.UNMOUNT

# Helper values for user-space events
IN_CLOSE = IN_CLOSE_WRITE | IN_CLOSE_NOWRITE
IN_MOVE = IN_MOVED_FROM | IN_MOVED_TO

# All user-space events.
IN_ALL_EVENTS = six.moves.reduce(operator.or_, [
    IN_ACCESS,
    IN_ATTRIB,
    IN_CLOSE_NOWRITE,
    IN_CLOSE_WRITE,
    IN_CREATE,
    IN_DELETE,
    IN_DELETE_SELF,
    IN_MODIFY,
    IN_MOVED_FROM,
    IN_MOVED_TO,
    IN_MOVE_SELF,
    IN_OPEN,
])


def _fmt_mask(mask):
    """Parse an Inotify event mask into indivitual event flags."""
    masks = []
    # Non-iterable value INEvent is used in an iterating context
    for event in INEvent:
        if mask & event:
            masks.append(event.name)
            mask ^= event
    if mask:
        masks.append(hex(mask))
    return masks


###############################################################################
# High level Python API
class InotifyEvent(collections.namedtuple('InotifyEvent',
                                          'wd mask cookie src_path')):
    """
    Inotify event struct wrapper.

    :param wd:
        Watch descriptor
    :param mask:
        Event mask
    :param cookie:
        Event cookie
    :param src_path:
        Event source path
    """
    __slots__ = ()

    @property
    def is_modify(self):
        """Test mask shorthand."""
        return bool(self.mask & IN_MODIFY)

    @property
    def is_close_write(self):
        """Test mask shorthand."""
        return bool(self.mask & IN_CLOSE_WRITE)

    @property
    def is_close_nowrite(self):
        """Test mask shorthand."""
        return bool(self.mask & IN_CLOSE_NOWRITE)

    @property
    def is_access(self):
        """Test mask shorthand."""
        return bool(self.mask & IN_ACCESS)

    @property
    def is_delete(self):
        """Test mask shorthand."""
        return bool(self.mask & IN_DELETE)

    @property
    def is_delete_self(self):
        """Test mask shorthand."""
        return bool(self.mask & IN_DELETE_SELF)

    @property
    def is_create(self):
        """Test mask shorthand."""
        return bool(self.mask & IN_CREATE)

    @property
    def is_moved_from(self):
        """Test mask shorthand."""
        return bool(self.mask & IN_MOVED_FROM)

    @property
    def is_moved_to(self):
        """Test mask shorthand."""
        return bool(self.mask & IN_MOVED_TO)

    @property
    def is_move(self):
        """Test mask shorthand."""
        return bool(self.mask & IN_MOVE)

    @property
    def is_move_self(self):
        """Test mask shorthand."""
        return bool(self.mask & IN_MOVE_SELF)

    @property
    def is_attrib(self):
        """Test mask shorthand."""
        return bool(self.mask & IN_ATTRIB)

    @property
    def is_ignored(self):
        """Test mask shorthand."""
        return bool(self.mask & IN_IGNORED)

    @property
    def is_directory(self):
        """Test mask shorthand."""
        return bool(self.mask & IN_ISDIR)

    def __repr__(self):
        masks = _fmt_mask(self.mask)
        return ('<InotifyEvent: src_path=%s, wd=%d, mask=%s, cookie=%d>') % (
            self.src_path,
            self.wd,
            '|'.join(masks),
            self.cookie,
        )


DEFAULT_NUM_EVENTS = 2048
DEFAULT_EVENT_BUFFER_SIZE = DEFAULT_NUM_EVENTS * INOTIFY_EVENT_HDRSIZE


class Inotify:
    """Inotify system interface."""

    def __init__(self, flags):
        """Initialize a new Inotify object.
        """
        # The file descriptor associated with the inotify instance.
        inotify_fd = inotify_init(flags)
        self._inotify_fd = inotify_fd
        self._paths = {}

    def fileno(self):
        """The file descriptor associated with the inotify instance."""
        return self._inotify_fd

    def close(self):
        """Close the inotify filedescriptor.

        NOTE: After call this, this object will be unusable.
        """
        os.close(self._inotify_fd)

    def add_watch(self, path, event_mask=IN_ALL_EVENTS):
        """
        Adds a watch for the given path to monitor events specified by the
        mask.

        :param path:
            Path to monitor
        :type path:
            ``str``
        :param event_mask:
            *optional* Bit mask of the request events.
        :type event_mask:
            ``int``
        :returns:
            Unique watch descriptor identifier
        :rtype:
            ``int``
        """
        path = os.path.normpath(path)
        watch_id = inotify_add_watch(
            self._inotify_fd,
            path,
            event_mask | IN_MASK_ADD
        )
        self._paths[watch_id] = path
        return watch_id

    def remove_watch(self, watch_id):
        """
        Removes a watch.

        :param watch_id:
            Watch descriptor returned by :meth:`~Inotify.add_watch`
        :type watch_id:
            ``int``
        :returns:
            ``None``
        """
        inotify_rm_watch(self._inotify_fd, watch_id)

    def read_events(self, event_buffer_size=DEFAULT_EVENT_BUFFER_SIZE):
        """
        Reads events from inotify and yields them.

        :param event_buffer_size:
            *optional* Buffer size while reading the inotify socket
        :type event_buffer_size:
            ``int``
        :returns:
            List of :class:`InotifyEvent` instances
        :rtype:
            ``list``
        """
        if not self._paths:
            return []
        event_buffer = os.read(self._inotify_fd, event_buffer_size)
        event_list = []
        for wd, mask, cookie, name in _parse_buffer(event_buffer):
            name = name.decode()
            wd_path = self._paths[wd]
            src_path = os.path.normpath(os.path.join(wd_path, name))
            inotify_event = InotifyEvent(wd, mask, cookie, src_path)
            _LOGGER.debug('Received event %r', inotify_event)

            if inotify_event.mask & IN_IGNORED:
                # Clean up deleted watches
                del self._paths[wd]

            event_list.append(inotify_event)

        return event_list


###############################################################################
__all__ = [
    'IN_NONBLOCK',
    'IN_NONBLOCK',
    'IN_DONT_FOLLOW',
    'IN_MASK_ADD',
    'IN_ONESHOT',
    'IN_ONLYDIR',
    'IN_ACCESS',
    'IN_ATTRIB',
    'IN_CLOSE_WRITE',
    'IN_CLOSE_NOWRITE',
    'IN_CREATE',
    'IN_DELETE',
    'IN_DELETE_SELF',
    'IN_MODIFY',
    'IN_MOVE_SELF',
    'IN_MOVED_FROM',
    'IN_MOVED_TO',
    'IN_OPEN',
    'IN_IGNORED',
    'IN_ISDIR',
    'IN_Q_OVERFLOW',
    'IN_UNMOUNT',
    'IN_CLOSE',
    'IN_MOVE',
    'IN_ALL_EVENTS',
    'inotify_init',
    'inotify_add_watch',
    'inotify_rm_watch',
    'Inotify',
    'InotifyEvent',
]
