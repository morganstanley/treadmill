"""Treadmill user util module."""


import os

if os.name != 'nt':
    import pwd
else:
    from .syscall import winapi


def is_root():
    """Gets whether the current user is root"""
    if os.name == 'nt':
        return winapi.is_user_admin()
    else:
        return os.geteuid() == 0


def get_current_username():
    """Returns the current user name"""
    if os.name == 'nt':
        return winapi.GetUserName()
    else:
        return pwd.getpwuid(os.getuid()).pw_name
