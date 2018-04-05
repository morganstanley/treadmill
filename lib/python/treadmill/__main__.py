"""Treadmill module launcher.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import importlib


if __name__ == '__main__':
    init_hook = os.environ.get('TREADMILL_INIT_HOOK')
    if init_hook:
        for module_name in init_hook.split(':'):
            importlib.import_module(module_name)

    from . import console
    # pylint complains "No value passed for parameter ... in function call".
    # This is ok, as these parameters come from click decorators.
    console.run()  # pylint: disable=no-value-for-parameter
