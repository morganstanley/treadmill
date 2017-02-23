"""An individual treadmill spawn instance."""
from __future__ import absolute_import

import logging
import os
import pwd
import subprocess
import time
import yaml

from treadmill import exc
from treadmill import spawn
from treadmill import fs
from treadmill import subproc
from treadmill.api import instance

_LOGGER = logging.getLogger(__name__)


class Instance(object):
    """Treadmill spawn instance"""

    __slots__ = (
        'root',
        'manifest_path',
        'zk_mirror_dir',
        'id',
        'proid',
        'name',
        'settings',
        'start_time',
        'manifest',
        'instance',
        'instance_no'
    )

    INSTANCE_FILE = 'data'

    def __init__(self, root, manifest_path):
        self.root = root
        self.manifest_path = manifest_path
        self.zk_mirror_dir = os.path.join(self.root, spawn.ZK_MIRROR_DIR)

        self.id = os.path.splitext(os.path.basename(self.manifest_path))[0]
        self.proid = self._get_user_safe(self.manifest_path)
        self.settings = {
            'name': self.id,
            'stop': True,
            'reconnect': 0
        }
        self.start_time = self._get_filetime_safe()

        self.manifest = None
        self.instance = None
        self.instance_no = None

        self._read_instance_file()
        self._read_manifest_file()

        self.name = '{0}.{1}'.format(self.proid, self.settings['name'])

        fs.mkdir_safe(self.zk_mirror_dir)

    def _get_user_safe(self, path):
        """Gets the user of the given path."""
        try:
            return pwd.getpwuid(os.stat(path).st_uid).pw_name
        except (OSError, KeyError):
            _LOGGER.warn('Could not get user of path %r', path)
            return None

    def _get_filetime_safe(self):
        """Gets the last modified time of the given path."""
        try:
            return os.path.getmtime(self.INSTANCE_FILE)
        except OSError:
            return 0

    def _parse_instance(self, inst):
        if inst is None:
            return False

        if "#" not in inst:
            _LOGGER.error('Invalid instance %r', inst)
            return False

        self.instance = inst.strip()
        self.instance_no = self.instance.split("#")[1]
        return True

    def _read_instance_file(self):
        """Reads the instance from the data file."""
        try:
            with open(self.INSTANCE_FILE, "r") as data:
                data_contents = data.read()
                self._parse_instance(data_contents)
        except IOError:
            pass

    def _write_instance_file(self, inst):
        """Writes the instance to the data file."""
        if self._parse_instance(inst):
            try:
                f = open(self.INSTANCE_FILE, 'w')
                f.write(self.instance)
                f.close()
                return True
            except IOError as ex:
                _LOGGER.warning(ex)

        return False

    def _read_manifest_file(self):
        """Reads the YAML (manifest) file contents."""
        docs = []

        try:
            stream = open(self.manifest_path, "r")
            manifest_contents = stream.read()
            generator = yaml.load_all(manifest_contents)

            for doc in generator:
                docs.append(doc)
        except (IOError, yaml.YAMLError) as ex:
            _LOGGER.error(ex)
            return

        if len(docs) < 2:
            _LOGGER.error("YAML file needs to contain 2 docs")
            return

        self.settings.update(docs[0])
        self.manifest = docs[1]

    def _remove_instance_file(self):
        """"Removes the data file if it exists."""
        fs.rm_safe(self.INSTANCE_FILE)

        self.instance = None
        self.instance_no = None

    def remove_manifest(self):
        """"Removes the manifest file if it exists."""
        if self.instance is not None:
            reconnect = self.settings['reconnect']
            if reconnect != 0:
                should_remove = False
                if reconnect > 0:
                    diff = time.time() - self.start_time
                    should_remove = diff >= reconnect

                if not should_remove:
                    _LOGGER.info("Waiting for reconnect!")
                    return

            self._remove_instance_file()

        _LOGGER.info("Removing instance!")

        try:
            subproc.check_call(['s6-svc', '-O', os.getcwd()])
        except subprocess.CalledProcessError as ex:
            _LOGGER.warning(ex)

        fs.rm_safe(self.manifest_path)

    def run(self):
        """Invokes Treadmill instance create api."""
        if self.instance is not None:
            return True

        try:
            api = instance.API()
            return self._write_instance_file(
                api.create(self.name, self.manifest)[0])
        except (IOError, exc.TreadmillError) as ex:
            _LOGGER.error(ex)
            return False

    def stop(self, exit_code):
        """Calls Treadmill instance stop api."""
        if self.instance is None:
            return

        if exit_code != 0:
            if exit_code != 11 and not self.settings['stop']:
                return

            try:
                api = instance.API()
                api.delete(self.instance)
            except exc.TreadmillError as ex:
                _LOGGER.error(ex)
                return

        self._remove_instance_file()

    def get_watch_path(self):
        """Gets the watch path for fstrace."""
        return os.path.join(self.zk_mirror_dir, 'tasks',
                            self.name, self.instance_no)
