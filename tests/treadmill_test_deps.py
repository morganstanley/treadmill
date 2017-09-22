"""Treadmill tests dependencies.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys

if 'test_setup' not in sys.modules:
    import imp
    import os

    PROJ_DIR = os.path.realpath(
        os.path.join(
            os.path.dirname(__file__),
            os.path.pardir,
        )
    )
    imp.load_source('test_setup',
                    os.path.join(PROJ_DIR, 'test_setup.py'))
