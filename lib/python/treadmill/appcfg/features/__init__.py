"""Treadmill features.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from treadmill import plugin_manager


def list_all_features():
    """Lists all feature names."""
    return plugin_manager.names('treadmill.features')


def feature_exists(feature):
    """Tests if the feature exists."""
    return feature in plugin_manager.names('treadmill.features')


def get_feature(feature):
    """Gets the feature with the given name."""
    if not feature_exists(feature):
        return None

    return plugin_manager.load('treadmill.features', feature)
