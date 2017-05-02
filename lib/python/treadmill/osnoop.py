"""Will do nothing for the given os."""

from __future__ import absolute_import

import os


def linux(func):
    """Decorator function for executing function only on linux"""
    def func_wrapper(*args, **kwargs):
        """Wrapper function"""
        if os.name != 'posix':
            return func(*args, **kwargs)
    return func_wrapper


def windows(func):
    """Decorator function for executing function only on windows"""
    def func_wrapper(*args, **kwargs):
        """Wrapper function"""
        if os.name != 'nt':
            return func(*args, **kwargs)
    return func_wrapper
