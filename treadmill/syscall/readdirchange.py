"""Windows directory watcher API wrapper module
"""

import ctypes.wintypes
import os
import queue
import select
import _thread
import threading
from functools import reduce


# Windows constatns
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

FILE_NOTIFY_CHANGE_FILE_NAME = 0x01
FILE_NOTIFY_CHANGE_DIR_NAME = 0x02
FILE_NOTIFY_CHANGE_ATTRIBUTES = 0x04
FILE_NOTIFY_CHANGE_SIZE = 0x08
FILE_NOTIFY_CHANGE_LAST_WRITE = 0x010
FILE_NOTIFY_CHANGE_LAST_ACCESS = 0x020
FILE_NOTIFY_CHANGE_CREATION = 0x040
FILE_NOTIFY_CHANGE_SECURITY = 0x0100

FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_FLAG_OVERLAPPED = 0x40000000
FILE_LIST_DIRECTORY = 0x01
FILE_SHARE_READ = 0x01
FILE_SHARE_WRITE = 0x02
FILE_SHARE_DELETE = 0x04
OPEN_EXISTING = 3

FILE_ACTION_CREATED = 1
FILE_ACTION_DELETED = 2
FILE_ACTION_MODIFIED = 3
FILE_ACTION_RENAMED_OLD_NAME = 4
FILE_ACTION_RENAMED_NEW_NAME = 5
FILE_ACTION_OVERFLOW = 0xFFFF


class OVERLAPPED(ctypes.Structure):
    """Structure for async IO."""

    _fields_ = [('Internal', ctypes.c_void_p),
                ('InternalHigh', ctypes.c_void_p),
                ('Offset', ctypes.wintypes.DWORD),
                ('OffsetHigh', ctypes.wintypes.DWORD),
                ('Pointer', ctypes.c_void_p),
                ('hEvent', ctypes.wintypes.HANDLE), ]


def _errcheck_bool(value, func, args):  # pylint: disable=W0613
    """Helper function for checking bool value."""

    if not value:
        raise ctypes.WinError()
    return args


def _errcheck_handle(value, func, args):  # pylint: disable=W0613
    """Helper function for checking handle value."""

    if not value:
        raise ctypes.WinError()
    if value == INVALID_HANDLE_VALUE:
        raise ctypes.WinError()
    return args


def _errcheck_dword(value, func, args):  # pylint: disable=W0613
    """Helper function for checking DWORD value."""

    if value == 0xFFFFFFFF:
        raise ctypes.WinError()
    return args


# pylint: disable=C0103
ReadDirectoryChangesW = ctypes.windll.kernel32.ReadDirectoryChangesW
ReadDirectoryChangesW.restype = ctypes.wintypes.BOOL
ReadDirectoryChangesW.errcheck = _errcheck_bool
ReadDirectoryChangesW.argtypes = (
    ctypes.wintypes.HANDLE,  # hDirectory
    ctypes.c_void_p,  # lpBuffer
    ctypes.wintypes.DWORD,  # nBufferLength
    ctypes.wintypes.BOOL,  # bWatchSubtree
    ctypes.wintypes.DWORD,  # dwNotifyFilter
    ctypes.POINTER(ctypes.wintypes.DWORD),  # lpBytesReturned
    ctypes.POINTER(OVERLAPPED),  # lpOverlapped
    ctypes.c_void_p  # FileIOCompletionRoutine # lpCompletionRoutine
)

# pylint: disable=C0103
CreateFileW = ctypes.windll.kernel32.CreateFileW
CreateFileW.restype = ctypes.wintypes.HANDLE
CreateFileW.errcheck = _errcheck_handle
CreateFileW.argtypes = (
    ctypes.wintypes.LPCWSTR,  # lpFileName
    ctypes.wintypes.DWORD,  # dwDesiredAccess
    ctypes.wintypes.DWORD,  # dwShareMode
    ctypes.c_void_p,  # lpSecurityAttributes
    ctypes.wintypes.DWORD,  # dwCreationDisposition
    ctypes.wintypes.DWORD,  # dwFlagsAndAttributes
    ctypes.wintypes.HANDLE  # hTemplateFile
)

# pylint: disable=C0103
CloseHandle = ctypes.windll.kernel32.CloseHandle
CloseHandle.restype = ctypes.wintypes.BOOL
CloseHandle.argtypes = (
    ctypes.wintypes.HANDLE,  # hObject
)

# pylint: disable=C0103
CancelIoEx = ctypes.windll.kernel32.CancelIoEx
CancelIoEx.restype = ctypes.wintypes.BOOL
CancelIoEx.errcheck = _errcheck_bool
CancelIoEx.argtypes = (
    ctypes.wintypes.HANDLE,  # hObject
    ctypes.POINTER(OVERLAPPED)  # lpOverlapped
)


# pylint: disable=C0103
class FILE_NOTIFY_INFORMATION(ctypes.Structure):
    """Info for file notification."""

    _fields_ = [("NextEntryOffset", ctypes.wintypes.DWORD),
                ("Action", ctypes.wintypes.DWORD),
                ("FileNameLength", ctypes.wintypes.DWORD),
                ("FileName", (ctypes.c_char * 1))]


PFILE_NOTIFY_INFORMATION = ctypes.POINTER(FILE_NOTIFY_INFORMATION)


WATCHDOG_FILE_FLAGS = FILE_FLAG_BACKUP_SEMANTICS
WATCHDOG_FILE_SHARE_FLAGS = reduce(
    lambda x, y: x | y, [
        FILE_SHARE_READ,
        FILE_SHARE_WRITE,
        FILE_SHARE_DELETE,
    ])
WATCHDOG_FILE_NOTIFY_FLAGS = reduce(
    lambda x, y: x | y, [
        FILE_NOTIFY_CHANGE_FILE_NAME,
        FILE_NOTIFY_CHANGE_DIR_NAME,
        FILE_NOTIFY_CHANGE_ATTRIBUTES,
        FILE_NOTIFY_CHANGE_SIZE,
        FILE_NOTIFY_CHANGE_LAST_WRITE,
        FILE_NOTIFY_CHANGE_SECURITY,
        FILE_NOTIFY_CHANGE_LAST_ACCESS,
        FILE_NOTIFY_CHANGE_CREATION,
    ])

BUFFER_SIZE = 2048


class InotifyEvent(object):
    """Event class for file change."""

    def __init__(self, action, src_path):
        """Initialize a new InotifyEvent object."""
        self.action = action
        self.src_path = src_path

    @property
    def is_create(self):
        """Returns true if the file was created."""
        return self.action == FILE_ACTION_CREATED

    @property
    def is_attrib(self):
        """Returns true if the file attribute was created."""
        return self.is_modify

    @property
    def is_delete(self):
        """Returns true if the file was deleted."""
        return self.action == FILE_ACTION_DELETED

    @property
    def is_delete_self(self):
        """Returns true if the file was deleted."""
        return self.is_delete

    @property
    def is_modify(self):
        """Returns true if the file was modified."""
        return self.action == FILE_ACTION_MODIFIED

    @property
    def is_moved_from(self):
        """Returns true if the file was moved."""
        return self.action == FILE_ACTION_RENAMED_OLD_NAME

    @property
    def is_moved_to(self):
        """Returns true if the file was moved."""
        return self.action == FILE_ACTION_RENAMED_NEW_NAME

    @property
    def is_close_write(self):
        """Returns false. Not used."""
        return False

    @property
    def is_close_nowrite(self):
        """Returns false. Not used."""
        return False

    @property
    def is_access(self):
        """Returns false. Not used."""
        return False

    @property
    def is_move(self):
        """Returns true if the file was moved."""
        return self.is_moved_from or self.is_moved_to

    @property
    def is_move_self(self):
        """Returns false. Not used."""
        return False

    @property
    def is_ignored(self):
        """Returns false. Not used."""
        return False

    @property
    def is_directory(self):
        """Returns false. Not used."""
        return False


class ReadDirChange(object):
    """ReadDirectoryChangesW system interface."""

    def __init__(self):
        """Initialize a new ReadDirChange object.
        """
        self._path = ""
        self._handle = 0
        self._shouldexit = False
        self._eventsqueue = queue.Queue(100)
        self._waitevent = threading.Event()

    def fileno(self):
        """The directory handle associated with the inotify instance."""
        return self._handle

    def close(self):
        """Close the inotify directory handle.

        NOTE: After call this, this object will be unusable.
        """
        self._shouldexit = True
        try:
            CancelIoEx(self._handle, None)
        except:  # pylint: disable=W0702
            pass

        try:
            CloseHandle(self._handle)
        except:  # pylint: disable=W0702
            pass

    def add_watch(self, path):
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
        self._path = os.path.normpath(path)
        self._handle = CreateFileW(self._path,
                                   FILE_LIST_DIRECTORY,
                                   WATCHDOG_FILE_SHARE_FLAGS,
                                   None, OPEN_EXISTING,
                                   WATCHDOG_FILE_FLAGS,
                                   None)
        _thread.start_new_thread(self._read_events_tread_proc, ())
        return self._handle

    def remove_watch(self, watch_id):  # pylint: disable=W0613
        """
        Removes a watch.

        :param watch_id:
            Watch descriptor returned by :meth:`~Inotify.add_watch`
        :type watch_id:
            ``int``
        :returns:
            ``None``
        """
        self.close()

    def wait(self, timeout):
        """wait for file changes."""

        if timeout == -1:
            result = self._waitevent.wait()
        else:
            result = self._waitevent.wait(float(timeout / 1000))
        if result:
            self._waitevent.clear()
        return result

    def _read_events_tread_proc(self, *args):  # pylint: disable=W0613
        """Thread function to monitor file changes."""

        while True:
            events = self._get_directory_change_events()
            if not events:
                continue
            for event in events:
                self._eventsqueue.put(event)
            self._waitevent.set()

    def _get_directory_change_events(self):
        """Gets changes to the directory."""

        event_buffer = ctypes.create_string_buffer(BUFFER_SIZE)
        nbytes = ctypes.wintypes.DWORD()
        ReadDirectoryChangesW(self._handle,
                              ctypes.byref(event_buffer),
                              len(event_buffer),
                              True,
                              WATCHDOG_FILE_NOTIFY_FLAGS,
                              ctypes.byref(nbytes),
                              None,
                              None)

        events = self._create_events_from_byte_array(event_buffer.raw,
                                                     int(nbytes.value))

        return [InotifyEvent(action, os.path.join(self._path, path))
                for action, path in events]

    def _create_events_from_byte_array(self, event_buffer, buffer_len):
        """Parse the file change event buffer."""

        results = []
        while buffer_len > 0:
            pfni = ctypes.cast(event_buffer, PFILE_NOTIFY_INFORMATION)[0]

            offset = FILE_NOTIFY_INFORMATION.FileName.offset
            ptr = ctypes.addressof(pfni) + offset

            filename_unicode = ctypes.string_at(ptr, pfni.FileNameLength)
            filename_ascii = filename_unicode.decode('utf-16')

            results.append((pfni.Action, filename_ascii))

            numToSkip = pfni.NextEntryOffset
            if numToSkip <= 0:
                break
            event_buffer = event_buffer[numToSkip:]
            buffer_len -= numToSkip
        return results

    # pylint: disable=W0613
    def read_events(self, event_buffer_size=BUFFER_SIZE):
        """
        Reads events from inotify and yields them.

        :param event_buffer_size:
            not used
        :type event_buffer_size:
            ``int``
        :returns:
            List of :class:`InotifyEvent` instances
        :rtype:
            ``list``
        """
        if self._eventsqueue.empty():
            return []
        event_list = []

        while not self._eventsqueue.empty():
            event = self._eventsqueue.get(False)
            event_list.append(event)
        return event_list


class Poll(object):
    """Helper class for poll."""

    def __init__(self):
        """Initialize a new InotifyEvent object."""

        self._inotify = None
        self._mask = 0

    def register(self, inotify, mask):
        """Register poll."""

        self._inotify = inotify
        self._mask = mask

    def poll(self, timeout):
        """Polls for changes."""

        return self._inotify.wait(timeout)


def poll():
    """Creates a new poll object."""

    return Poll()


select.poll = poll
select.POLLIN = 1
