"""Treadmill image."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


from treadmill import appcfg

from . import native
from . import tar


def get_image_repo(tm_env, app_type):
    """Gets the image repository for the given app type or None if it is
    invalid.
    """
    if app_type == appcfg.AppType.NATIVE:
        return native.NativeImageRepository(tm_env)

    if app_type == appcfg.AppType.TAR:
        return tar.TarImageRepository(tm_env)

    return None


def get_image(tm_env, manifest):
    """Gets am image from the given manifest."""
    app_type = appcfg.AppType(manifest.get('type'))
    image_repo = get_image_repo(tm_env, app_type)

    if image_repo is None:
        raise Exception(
            'There is no repository for app with type {0}.'.format(
                app_type
            )
        )

    img_impl = image_repo.get(manifest.get('image'))

    if img_impl is None:
        raise Exception(
            'There is no image {0} for app with type {1}.'.format(
                manifest.get('image'), app_type
            )
        )

    return img_impl


__all__ = [
    'get_image_repo',
    'get_image'
]
