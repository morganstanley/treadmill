"""Will do nothing for the given OS.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os


def linux(func):
    """Decorator function for executing function only on linux"""
    def func_wrapper(*args, **kwargs):
        """Wrapper function"""
        if os.name != 'posix':
            return func(*args, **kwargs)
        else:
            return None
    return func_wrapper


def windows(func):
    """Decorator function for executing function only on windows"""
    def func_wrapper(*args, **kwargs):
        """Wrapper function"""
        if os.name != 'nt':
            return func(*args, **kwargs)
        else:
            return None
    return func_wrapper
