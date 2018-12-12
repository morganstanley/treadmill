"""A collection of TAR images.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import hashlib
import io
import logging
import os
import shutil
import tarfile
import tempfile

import requests
import requests_kerberos

from six.moves import urllib_parse

from treadmill import fs

from . import _image_base
from . import _repository_base
from . import native

_LOGGER = logging.getLogger(__name__)

TAR_DIR = 'tar'


def _download(url, temp):
    """Downloads the image."""
    _LOGGER.debug('Downloading tar file from %r to %r.', url, temp)

    krb_auth = requests_kerberos.HTTPKerberosAuth(
        mutual_authentication=requests_kerberos.DISABLED,
        # kerberos 1.2.5 doesn't accept None principal. Remove this once fixed.
        principal=''
    )

    request = requests.get(url, stream=True, auth=krb_auth)
    shutil.copyfileobj(request.raw, temp)


def _copy(path, temp):
    """Copies the image."""
    _LOGGER.debug('Copying tar file from %r to %r.', path, temp)
    with io.open(path, 'rb') as f:
        shutil.copyfileobj(f, temp)


def _sha256sum(path):
    """Calculates the SHA256 hash of the file."""
    sha256 = hashlib.sha256()

    with io.open(path, 'rb') as f:
        for block in iter(lambda: f.read(sha256.block_size), b''):
            sha256.update(block)

    return sha256.hexdigest()


class TarImage(_image_base.Image):
    """Represents a TAR image."""

    __slots__ = (
        'tm_env',
        'image_path',
    )

    def __init__(self, tm_env, image_path):
        self.tm_env = tm_env
        self.image_path = image_path

    def unpack(self, container_dir, root_dir, app, app_cgroups):
        _LOGGER.debug('Extracting tar file %r to %r.', self.image_path,
                      root_dir)
        with tarfile.open(self.image_path) as tar:
            tar.extractall(path=root_dir)

        native.NativeImage(self.tm_env).unpack(
            container_dir, root_dir, app, app_cgroups
        )

        # TODO: cache instead of removing TAR files.
        fs.rm_safe(self.image_path)


class TarImageRepository(_repository_base.ImageRepository):
    """A collection of TAR images."""

    def get(self, url):
        images_dir = os.path.join(self.tm_env.images_dir, TAR_DIR)
        fs.mkdir_safe(images_dir)

        image = urllib_parse.urlparse(url)
        sha256 = urllib_parse.parse_qs(image.query).get('sha256', None)

        with tempfile.NamedTemporaryFile(dir=images_dir, delete=False,
                                         prefix='.tmp') as temp:
            if image.scheme == 'http':
                _download(url, temp)
            else:
                _copy(image.path, temp)

        if not tarfile.is_tarfile(temp.name):
            _LOGGER.error('File %r is not a tar file.', url)
            raise Exception('File {0} is not a tar file.'.format(url))

        new_sha256 = _sha256sum(temp.name)

        if sha256 is not None and sha256[0] != new_sha256:
            _LOGGER.error('Hash does not match %r - %r', sha256[0], new_sha256)
            raise Exception(
                'Hash of {0} does not match {1}.'.format(new_sha256, url))

        # TODO: rename tar file to sha256 to allow for caching.
        return TarImage(self.tm_env, temp.name)
