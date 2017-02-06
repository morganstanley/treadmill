"""Treadmill festures"""

import sys
import pkgutil

import jsonschema.exceptions  # noqa: F401

from treadmill import utils


__path__ = pkgutil.extend_path(__path__, __name__)

_THIS_MOD = sys.modules[__name__]

ALL_FEATURES = set(utils.modules_in_pkg(_THIS_MOD))
