"""Windows API function wrappers
"""

import os

import ctypes
import ctypes.wintypes


assert os.name == 'nt'


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
