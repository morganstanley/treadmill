"""An individual treadmill spawn instance.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import logging
import os

from treadmill.spawn import utils as spawn_utils
from treadmill import yamlwrapper as yaml

_LOGGER = logging.getLogger(__name__)


class Instance:
    """Treadmill spawn instance"""

    __slots__ = (
        'id',
        'proid',
        'name',
        'settings',
        'manifest',
        'manifest_path'
    )

    def __init__(self, manifest_path):
        self.manifest_path = manifest_path
        self.id = os.path.splitext(os.path.basename(self.manifest_path))[0]
        self.proid = spawn_utils.get_user_safe(self.manifest_path)
        self.settings = {
            'name': self.id,
            'stop': True,
            'reconnect': False,
            'reconnect_timeout': 0
        }
        self.manifest = None

        self._read_manifest_file()

        self.name = '{0}.{1}'.format(self.proid, self.settings['name'])

    def _read_manifest_file(self):
        """Reads the YAML (manifest) file contents."""
        docs = []

        try:
            stream = io.open(self.manifest_path, 'r')
            manifest_contents = stream.read()
            generator = yaml.load_all(manifest_contents)

            for doc in generator:
                docs.append(doc)
        except (IOError, yaml.YAMLError) as ex:
            _LOGGER.error(ex)
            return

        if len(docs) < 2:
            _LOGGER.error('YAML file needs to contain 2 docs')
            return

        self.settings.update(docs[0])
        self.manifest = docs[1]

        if self.manifest is None:
            self.manifest = {}
