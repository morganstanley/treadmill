"""Treadmill AFS plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import itertools
import logging
import os
import random

import requests
import six

from six.moves import configparser

from treadmill import dist
from treadmill import fs
from treadmill import subproc
from treadmill.fs import linux as fs_linux
from treadmill.runtime.linux.image import fs as image_fs

_LOGGER = logging.getLogger(__name__)

#: AFS client file representing current cell
_AFS_THISCELL_FILE = os.path.join(
    '/', 'etc', 'vice', 'etc', 'ThisCell'
)


#: VMS REST interface for AFS cell query
_PORTAL_URL_TMPL = (
    'http://vmsportal.webfarm.ms.com/api/targets?location={location}'
    '&status=ok&fields=location,environment'
)

#: AFS environment mapping
_AFS_ENVIRONMENTS = {
    'dev': 'test',
    'qa': 'qa',
    'uat': 'qa',
    'prod': 'prod',
}

#: Name of the plugin config file
_PLUGIN_CONFIG = 'afs_plugin.ini'


class AFSFilesystemPlugin(image_fs.FilesystemPluginBase):
    """Configures afs given container environment."""

    __slots__ = (
        '_config_file',
    )

    def __init__(self, tm_env):
        super(AFSFilesystemPlugin, self).__init__(tm_env)
        self._config_file = os.path.join(tm_env.configs_dir, _PLUGIN_CONFIG)

    def init(self):
        """Resolve and ready all AFS targets.
        """
        my_cell = _my_cell()
        targets = _afs_targets(my_cell)
        # Since the targets are already randomized, we simply pick the first
        # one for each environment.
        targets = {
            env: {'name': targets[env][0]['name']}
            for env in targets
        }
        _LOGGER.info('AFS targets for this node: %r', targets)
        _activate_setuid(targets)

        afs_config = configparser.SafeConfigParser()
        afs_config.add_section('afs_targets')
        for env in _AFS_ENVIRONMENTS:
            afs_env = _AFS_ENVIRONMENTS[env]
            afs_config.set(
                'afs_targets',
                env,
                targets[afs_env]['name']
            )
        fs.write_safe(
            self._config_file,
            afs_config.write,
            mode='w',
            permission=0o644
        )

    def configure(self, container_dir, app):
        cp = configparser.SafeConfigParser()
        with io.open(self._config_file) as f:
            cp.readfp(f)  # pylint: disable=deprecated-method

        afs_env_target = cp.get('afs_targets', app.environment)
        afs_env_mount = _target_path(afs_env_target)

        mounts = {
            '/ms/dist': os.path.join(afs_env_mount, 'dist'),
            '/ms/user': '/ms/.user.prod',
            '/ms/.global': '/ms/.global',
        }

        nonprod_mounts = {
            '/ms/dist': os.path.join(afs_env_mount, 'dist'),
            '/ms/dev': '/ms/.dev',
            '/ms/user': '/ms/.user.dev',
            '/ms/group': '/ms/.group',
        }

        # Record the selected cell in the ak5log config
        thiscell_overlay = os.path.join(
            container_dir,
            'overlay',
            _AFS_THISCELL_FILE[1:],  # Remove leading '/'
        )
        fs.mkdir_safe(os.path.dirname(thiscell_overlay))
        with io.open(thiscell_overlay, 'w') as f:
            f.write(afs_env_target)

        if app.environment != 'prod':
            # Add supplementary / alternative DEV AFS mount points.
            for directory, mount in six.iteritems(nonprod_mounts):
                if os.path.exists(mount):
                    mounts[directory] = nonprod_mounts[directory]

                else:
                    if directory in mounts:
                        _LOGGER.warning('%r is not available. Container will'
                                        ' use PROD alternative.', mount)
                    else:
                        _LOGGER.warning('%r is not available. Container will'
                                        ' not have access to %r.', mount,
                                        directory)

        root_dir = os.path.join(container_dir, 'root')
        newroot_norm = fs.norm_safe(root_dir)
        for directory, mount in six.iteritems(mounts):
            fs.mkdir_safe(newroot_norm + directory)
            fs_linux.mount_bind(newroot_norm, directory, mount)

        fs_linux.mount_bind(
            newroot_norm,
            _AFS_THISCELL_FILE,
            thiscell_overlay
        )


def _afs_portal_query(location):
    """Query the VMS portable for cell availability in a given location.

    :param ``str`` location:
        SYS_LOC location string
    :returns ``dict``:
        Dictionnary of environment to list of AFS targets. Each target is a
        dictionary with (at least) a `name` key.
    """
    url = _PORTAL_URL_TMPL.format(location=location)
    query = requests.get(url)
    results = sorted(query.json()['items'], key=lambda x: x['environment'])
    # Turn the result list into a dictionnary of {env: targets}
    targets = {env: [] for env in _AFS_ENVIRONMENTS.values()}
    for env, info in itertools.groupby(results, lambda x: x['environment']):
        if env not in targets:
            continue
        targets.setdefault(env, []).extend(list(info))
    return targets


def _afs_targets(fallback_cell):
    """Resolve all AFS target in the current location.
    """
    my_loc = os.environ['SYS_LOC']
    targets = _afs_portal_query(my_loc)

    # If we do not have targets for all the environments, check the parent loc
    if not all((len(targets[env]) for env in targets)):
        parent_loc = my_loc.split('.', 1)[1]
        parent_targets = _afs_portal_query(parent_loc)

        for env in targets:
            if not targets[env]:
                if not parent_targets[env]:
                    _LOGGER.error('No target for %r found.'
                                  ' Falling back to node cell.', env)
                    targets[env] = [{'name': fallback_cell}]
                else:
                    _LOGGER.warning('No target for %r in %r.'
                                    ' Fallaing back to parent %r target.',
                                    env, my_loc, parent_loc)
                    targets[env] = parent_targets[env]

    for env in targets:
        random.shuffle(targets[env])
    _LOGGER.debug('Available AFS Targets in %r: %r', my_loc, targets)
    return targets


def _target_path(target_name):
    """Turn AFS target name into mount path.
    """
    return '/ms/.global/{llec}'.format(
        llec='.'.join(reversed(target_name[:-len('.ms.com')].split('.')))
    )


def _my_cell():
    """Read the currently configured AFS cell on the current host.
    """
    with io.open(_AFS_THISCELL_FILE) as f:
        cell = f.read().strip()
    return cell


def _activate_setuid(targets):
    """Activate setuid binaries on each of the provided targets.
    """
    _LOGGER.info('Enabling setuid binaries on %r', list(targets.values()))
    cells_list = list(
        itertools.chain.from_iterable(
            (
                ('--cell', target['name'])
                for target in targets.values()
            )
        )
    )
    subproc.check_call(['fs', 'setcell', '--suid'] + cells_list)


class MinimalAFSFilesystemPlugin(image_fs.FilesystemPluginBase):
    """Configures minimal fs."""

    def init(self):
        pass

    def configure(self, container_dir, app):
        treadmill_bind = subproc.resolve('treadmill_bind_distro')
        treadmill_pid1 = subproc.resolve('pid1_distro')

        mounts = [
            dist.TREADMILL,
            treadmill_bind,
            treadmill_pid1,
            '/ms/dist/cloud/PROJ/s6/2.6.0.0',
            '/ms/dist/sec/PROJ/openssh/5.8p2-ms2',
            '/ms/dist/sec/PROJ/openssl/1.0.0',
            '/ms/dist/aurora/PROJ/zlib/1.2',
            '/ms/dist/kerberos/PROJ/mitkrb5/1.4-lib-prod',
            '/ms/dist/kerberos/PROJ/conf',
            '/ms/dist/afs/PROJ/pam_ms_afs/3.1',
            '/ms/dist/sec/PROJ/pam_ms_krb5/4.3.3',
            '/ms/dist/pge/PROJ/pam_pge/1.1.2',
            '/ms/dist/fsf/PROJ/gcc-lib/3.4.5-2',
            '/ms/dist/pge/PROJ/core/3.1-5.10-64',
            '/ms/dist/pge/PROJ/tam/4.2.1-5.10',
            '/ms/dist/prolog/PROJ/pqi/1.3-5.10-64',
            '/ms/dist/prolog/PROJ/libfp/1.0-5.10',
            '/ms/dist/prolog/PROJ/swi/5.10.0',
            '/ms/dist/prolog/PROJ/tracer/3.1',
            '/ms/dist/prolog/PROJ/sqlite/2.0.3-5.10',
            '/ms/dist/prolog/PROJ/yaml/1.3.0-5.10',
            '/ms/dist/prolog/PROJ/proid/2.0',
            '/ms/dist/appmw/PROJ/tam-dcache-config',
            '/ms/dist/ebi/PROJ/yaml-cpp/0.1',
            '/ms/dist/fsf/PROJ/openldap/2.4-2.1-1.0.0',
            '/ms/dist/fsf/PROJ/sqlite/3.6.22',
            '/ms/dist/fsf/PROJ/boost/1.33.1-msparts5.0',
            '/ms/dist/environ/PROJ'
        ]

        root_dir = os.path.join(container_dir, 'root')
        newroot_norm = fs.norm_safe(root_dir)
        for mount in mounts:
            fs.mkdir_safe(newroot_norm + mount)
            fs_linux.mount_bind(newroot_norm, mount, mount)
