"""Treadmill features."""

import pkgutil

from treadmill import utils
from treadmill import plugin_manager


__path__ = pkgutil.extend_path(__path__, __name__)


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
