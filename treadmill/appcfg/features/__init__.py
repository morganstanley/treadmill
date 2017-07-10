"""Treadmill features."""

import pkgutil

from treadmill import plugin_manager


__path__ = pkgutil.extend_path(__path__, __name__)

_PLUGINS = plugin_manager.extensions('treadmill.features')


def list_all_features():
    """Lists all feature names."""
    return _PLUGINS().names()


def feature_exists(feature):
    """Tests if the feature exists."""
    return feature in _PLUGINS()


def get_feature(feature):
    """Gets the feature with the given name."""
    if not feature_exists(feature):
        return None

    return _PLUGINS()[feature].plugin()
