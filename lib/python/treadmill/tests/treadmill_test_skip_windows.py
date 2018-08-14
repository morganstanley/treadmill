"""Treadmill test skip windows.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import unittest

if os.name == 'nt':
    raise unittest.SkipTest("Test not applicable to Windows.")
