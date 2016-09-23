"""Treadmill tests dependencies."""

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
