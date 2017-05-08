"""Windows API function wrappers
"""

import os

import ctypes
import ctypes.wintypes


assert os.name == 'nt'


class MEMORYSTATUSEX(ctypes.Structure):
    """Contains information about the current state of both
    physical and virtual memory, including extended memory"""
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]

    def __init__(self):
        # have to initialize this to the size of MEMORYSTATUSEX
        # C0103: Invalid name "dwLength"
        # pylint: disable=C0103
        self.dwLength = ctypes.sizeof(self)
        super(MEMORYSTATUSEX, self).__init__()


class SID_IDENTIFIER_AUTHORITY(ctypes.Structure):  # pylint: disable=C0103
    """The SID_IDENTIFIER_AUTHORITY structure represents the top-level
    authority of a security identifier (SID)."""
    _fields_ = [
        ("byte0", ctypes.c_byte),
        ("byte1", ctypes.c_byte),
        ("byte2", ctypes.c_byte),
        ("byte3", ctypes.c_byte),
        ("byte4", ctypes.c_byte),
        ("byte5", ctypes.c_byte),
    ]

    def __init__(self, authority):
        self.byte5 = authority
        super(SID_IDENTIFIER_AUTHORITY, self).__init__()


def GetUserName():  # pylint: disable=C0103
    """Returns the current user name"""
    size = ctypes.pointer(ctypes.c_ulong(0))
    ctypes.windll.advapi32.GetUserNameA(None, size)

    user_buff = ctypes.create_string_buffer(size.contents.value)

    ctypes.windll.advapi32.GetUserNameA(user_buff, size)
    username = user_buff.value

    return username


def AllocateAndInitializeSid(pIdentifierAuthority,  # pylint: disable=C0103
                             nSubAuthorityCount,  # pylint: disable=C0103
                             dwSubAuthority0,  # pylint: disable=C0103
                             dwSubAuthority1,  # pylint: disable=C0103
                             dwSubAuthority2,  # pylint: disable=C0103
                             dwSubAuthority3,  # pylint: disable=C0103
                             dwSubAuthority4,  # pylint: disable=C0103
                             dwSubAuthority5,  # pylint: disable=C0103
                             dwSubAuthority6,  # pylint: disable=C0103
                             dwSubAuthority7):  # pylint: disable=C0103
    """he AllocateAndInitializeSid function allocates and initializes
    a security identifier (SID) with up to eight subauthorities."""

    sid = ctypes.c_void_p()

    apiresult = ctypes.windll.advapi32.AllocateAndInitializeSid(
        ctypes.byref(pIdentifierAuthority),
        nSubAuthorityCount,
        dwSubAuthority0,
        dwSubAuthority1,
        dwSubAuthority2,
        dwSubAuthority3,
        dwSubAuthority4,
        dwSubAuthority5,
        dwSubAuthority6,
        dwSubAuthority7,
        ctypes.byref(sid))
    if apiresult == 0:
        raise Exception("AllocateAndInitializeSid failed")

    return sid


def CheckTokenMembership(TokenHandle, SidToCheck):  # pylint: disable=C0103
    """The CheckTokenMembership function determines whether a specified
    security identifier (SID) is enabled in an access token. """
    is_admin = ctypes.wintypes.BOOL()
    apiresult = ctypes.windll.advapi32.CheckTokenMembership(
        TokenHandle,
        SidToCheck,
        ctypes.byref(is_admin))
    if apiresult == 0:
        raise Exception("CheckTokenMembership failed")

    return is_admin.value != 0


def FreeSid(pSid):  # pylint: disable=C0103
    """The FreeSid function frees a security identifier (SID)
    previously allocated by using the AllocateAndInitializeSid function."""
    ctypes.windll.advapi32.FreeSid(pSid)


def is_user_admin():
    """Gets whether the current user has administrator rights on windows"""

    if GetUserName() == 'system':
        return True

    nt_authority = SID_IDENTIFIER_AUTHORITY(5)
    SECURITY_BUILTIN_DOMAIN_RID = 0x20  # pylint: disable=C0103
    DOMAIN_ALIAS_RID_ADMINS = 0x220  # pylint: disable=C0103

    sid = AllocateAndInitializeSid(
        nt_authority,
        2,
        SECURITY_BUILTIN_DOMAIN_RID,
        DOMAIN_ALIAS_RID_ADMINS,
        0,
        0,
        0,
        0,
        0,
        0)

    try:
        return CheckTokenMembership(0, sid)
    finally:
        FreeSid(sid)


def GetDiskFreeSpaceExW(path):  # pylint: disable=C0103
    """Retrieves information about the amount of space that is available
    on a disk volume, which is the total amount of space, the total amount
    of free space, and the total amount of free space available to the user
    that is associated with the calling thread."""
    free = ctypes.c_ulonglong(0)
    total = ctypes.c_ulonglong(0)

    ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(path),
                                               None,
                                               ctypes.pointer(total),
                                               ctypes.pointer(free))
    return total.value, free.value


def GetTickCount64():  # pylint: disable=C0103
    """Retrieves the number of milliseconds that have elapsed
    since the system was started."""
    return ctypes.windll.kernel32.GetTickCount64()


def GlobalMemoryStatusEx():  # pylint: disable=C0103
    """Retrieves information about the system's current usage of
    both physical and virtual memory."""
    memory = MEMORYSTATUSEX()
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory))

    return memory
