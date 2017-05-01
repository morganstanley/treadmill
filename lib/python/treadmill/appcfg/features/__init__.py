"""Treadmill features."""

import pkgutil

from stevedore import extension


__path__ = pkgutil.extend_path(__path__, __name__)

_FEATURES_NAMESPACE = 'treadmill.features'
_FEATURES_EXTENSION_MANAGER = None


def _extension_manager():
    """Gets the extension manager for features."""
    # Disable W0603: Using the global statement
    global _FEATURES_EXTENSION_MANAGER  # pylint: disable=W0603
    if _FEATURES_EXTENSION_MANAGER is not None:
        return _FEATURES_EXTENSION_MANAGER

    _FEATURES_EXTENSION_MANAGER = extension.ExtensionManager(
        namespace=_FEATURES_NAMESPACE
    )

    return _FEATURES_EXTENSION_MANAGER


def list_all_features():
    """Lists all feature names."""
    return _extension_manager().names()


def feature_exists(feature):
    """Tests if the feature exists."""
    return feature in _extension_manager()


def get_feature(feature):
    """Gets the feature with the given name."""
    if not feature_exists(feature):
        return None

    return _extension_manager()[feature].plugin()
