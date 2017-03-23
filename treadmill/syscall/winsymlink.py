"""Module for handlinkg symlinks on windows"""

import ctypes.wintypes
import errno
import os
import struct

FSCTL_GET_REPARSE_POINT = 0x900a8
FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
GENERIC_READ = 0x80000000
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.wintypes.HANDLE(-1).value
INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF
FILE_FLAG_REPARSE_BACKUP = 0x2200000


def _errcheck_link(value, func, args):  # pylint: disable=W0613
    """Checks CreateSymbolicLinkW and CreateHardLinkW result"""
    # The windows api returns nonzero if the call was successful
    if value != 0:
        return

    last_error = ctypes.windll.kernel32.GetLastError()
    # Somehow CreateSymbolicLinkW and CreateHardLinkW retuns zero
    # and the last error is 2 (The system cannot find the file specified)
    # but the link is created successfuly
    # it seems like a bug in the WinAPI
    if last_error == 0 or last_error == 2:
        return
    if last_error == 183:
        raise OSError(errno.EEXIST,
                      "Cannot create a file when that file already exists",
                      args[0])


# pylint: disable=C0103
DeviceIoControl = ctypes.windll.kernel32.DeviceIoControl
DeviceIoControl.argtypes = [
    ctypes.wintypes.HANDLE,  # HANDLE hDevice
    ctypes.wintypes.DWORD,  # DWORD dwIoControlCode
    ctypes.wintypes.LPVOID,  # LPVOID lpInBuffer
    ctypes.wintypes.DWORD,  # DWORD nInBufferSize
    ctypes.wintypes.LPVOID,  # LPVOID lpOutBuffer
    ctypes.wintypes.DWORD,  # DWORD nOutBufferSize
    ctypes.POINTER(ctypes.wintypes.DWORD),  # LPDWORD lpBytesReturned
    ctypes.wintypes.LPVOID  # LPOVERLAPPED lpOverlapped
]
DeviceIoControl.restype = ctypes.wintypes.BOOL

# pylint: disable=C0103
CreateSymbolicLinkW = ctypes.windll.kernel32.CreateSymbolicLinkW
CreateSymbolicLinkW.argtypes = [
    ctypes.c_wchar_p,  # LPTSTR lpSymlinkFileName
    ctypes.c_wchar_p,  # LPTSTR lpTargetFileName
    ctypes.c_uint32  # DWORD dwFlags
]

CreateSymbolicLinkW.restype = ctypes.wintypes.BOOLEAN
CreateSymbolicLinkW.errcheck = _errcheck_link

# pylint: disable=C0103
CreateHardLinkW = ctypes.windll.kernel32.CreateHardLinkW
CreateHardLinkW.argtypes = [
    ctypes.c_wchar_p,  # LPCTSTR lpFileName
    ctypes.c_wchar_p,  # LPCTSTR lpExistingFileName
    ctypes.c_void_p  # LPSECURITY_ATTRIBUTES lpSecurityAttributes
]
CreateHardLinkW.restype = ctypes.wintypes.BOOL
CreateHardLinkW.errcheck = _errcheck_link


def _islink(path):
    """Gets whether the specified path is symlink"""
    if not os.path.isdir(path):
        return False

    if not isinstance(path, str):
        path = str(path)

    attributes = ctypes.windll.kernel32.GetFileAttributesW(path)
    if attributes == INVALID_FILE_ATTRIBUTES:
        return False

    return (attributes & FILE_ATTRIBUTE_REPARSE_POINT) > 0


def device_io_control(hDevice, ioControlCode, input_buffer, output_buffer):
    """Sends a control code directly to a specified device driver,
    causing the corresponding device to perform the corresponding operation"""
    if input_buffer:
        input_size = len(input_buffer)
    else:
        input_size = 0

    if isinstance(output_buffer, int):
        output_buffer = ctypes.create_string_buffer(output_buffer)

    output_size = len(output_buffer)
    assert isinstance(output_buffer, ctypes.Array)
    bytesReturned = ctypes.wintypes.DWORD()

    status = DeviceIoControl(hDevice, ioControlCode, input_buffer, input_size,
                             output_buffer, output_size, bytesReturned, None)

    if status != 0:
        return output_buffer[:bytesReturned.value]
    else:
        return None


def _readlink(path):
    """ Windows readlink implementation. """
    is_unicode = isinstance(path, str)

    if not is_unicode:
        path = str(path)

    if not _islink(path):
        raise OSError(errno.EINVAL, "Invalid argument", path)

    # Open the file correctly depending on the string type.
    hfile = ctypes.windll.kernel32.CreateFileW(path, GENERIC_READ, 0, None,
                                               OPEN_EXISTING,
                                               FILE_FLAG_REPARSE_BACKUP, None)

    if hfile == INVALID_HANDLE_VALUE:
        raise OSError(errno.ENOENT, "No such file or directory", path)

    # MAXIMUM_REPARSE_DATA_BUFFER_SIZE = 16384 = (16*1024)
    data_buffer = device_io_control(hfile, FSCTL_GET_REPARSE_POINT, None,
                                    16384)
    ctypes.windll.kernel32.CloseHandle(hfile)

    # Minimum possible length (assuming length of the target is bigger than 0)
    if not data_buffer or len(data_buffer) < 9:
        raise OSError(errno.ENOENT, "No such file or directory", path)

    # typedef struct _REPARSE_DATA_BUFFER {
    #   ULONG  ReparseTag;
    #   USHORT ReparseDataLength;
    #   USHORT Reserved;
    #   union {
    #       struct {
    #           USHORT SubstituteNameOffset;
    #           USHORT SubstituteNameLength;
    #           USHORT PrintNameOffset;
    #           USHORT PrintNameLength;
    #           ULONG Flags;
    #           WCHAR PathBuffer[1];
    #       } SymbolicLinkReparseBuffer;
    #       struct {
    #           USHORT SubstituteNameOffset;
    #           USHORT SubstituteNameLength;
    #           USHORT PrintNameOffset;
    #           USHORT PrintNameLength;
    #           WCHAR PathBuffer[1];
    #       } MountPointReparseBuffer;
    #       struct {
    #           UCHAR  DataBuffer[1];
    #       } GenericReparseBuffer;
    #   } DUMMYUNIONNAME;
    # } REPARSE_DATA_BUFFER, *PREPARSE_DATA_BUFFER;

    SymbolicLinkReparseFormat = 'LHHHHHHL'
    SymbolicLinkReparseSize = struct.calcsize(SymbolicLinkReparseFormat)

    # Only handle SymbolicLinkReparseBuffer
    # pylint: disable=W0612
    (tag, dataLength, reserver, SubstituteNameOffset, SubstituteNameLength,
     PrintNameOffset, PrintNameLength,
     Flags) = struct.unpack(SymbolicLinkReparseFormat,
                            data_buffer[:SymbolicLinkReparseSize])

    start = SubstituteNameOffset + SymbolicLinkReparseSize
    actualPath = \
        data_buffer[start: start + SubstituteNameLength].decode("utf-16")

    index = actualPath.find("\0")
    if index > 0:
        actualPath = actualPath[:index]

    if actualPath.startswith("\\??"):
        actualPath = actualPath[4:]

    if not is_unicode:
        return str(actualPath)

    return actualPath


def _link(filename, existing_filename):
    """symlink(source, link_name)
        Creates a symbolic link pointing to source named link_name"""
    CreateHardLinkW(filename, existing_filename, 0)


def _symlink(source, link_name):
    """symlink(source, link_name)
        Creates a symbolic link pointing to source named link_name"""
    flags = 0

    if source is not None and os.path.isdir(source):
        flags = 1

    CreateSymbolicLinkW(link_name, source, flags)


def _unlink(path):
    """Remove (delete) the file path."""
    if os.path.isdir(path):
        os.rmdir(path)
    else:
        os.remove(path)


os.symlink = _symlink
os.link = _link
os.readlink = _readlink
os.path.islink = _islink
os.unlink = _unlink
