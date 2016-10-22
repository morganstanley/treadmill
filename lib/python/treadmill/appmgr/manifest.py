"""Generation of Treadmill manifests from cell events."""
from __future__ import absolute_import

import importlib
import logging
import os

import yaml

from .. import appmgr
from .. import context
from .. import utils
from .. import subproc


_LOGGER = logging.getLogger(__name__)


def read(filename):
    """Standard way of reading a manifest.
    """
    with open(filename) as f:
        manifest = yaml.load(stream=f)

    return manifest


def load(tm_env, event):
    """Loads the app event file, ensuring it is in valid format, and supplement
    it into a full Treadmill manifest.

    :param event:
        Full path to the application node event in the zookeeper cache.
    :type event:
        ``str``
    :return:
        Application manifest object
    :rtype:
        ``dict``
    """
    # Disable pylint too many branches warning.
    # TODO: need better input validation / setting defaults process.
    #
    # pylint: disable=R0912
    name = os.path.basename(event)
    manifest = read(event)

    schema = [
        ('proid', True, str),
        ('services', True, list),
        ('endpoints', False, list),
        ('cpu', True, str),
        ('memory', True, str),
        ('disk', True, str),
    ]
    utils.validate(manifest, schema)
    manifest['system_services'] = []
    manifest['name'] = name
    manifest['app'] = appmgr.appname_basename(name)
    manifest['uniqueid'] = appmgr.gen_uniqueid(event)
    if 'environment' not in manifest:
        manifest['environment'] = 'dev'

    # TODO: probably need to throw exception rather than default to
    #                dev.
    if manifest['environment'] not in ['dev', 'qa', 'uat', 'prod']:
        _LOGGER.warn('Unrecognized environment: %s', manifest['environment'])
        manifest['environment'] = 'dev'

    if manifest['cpu'].endswith('%'):
        manifest['cpu'] = int(manifest['cpu'][:-1])

    # By default network is private.
    if 'shared_network' not in manifest:
        manifest['shared_network'] = False
    else:
        manifest['shared_network'] = bool(manifest['shared_network'])

    # By default host IP is not shared, not used in the container.
    if 'shared_ip' not in manifest:
        manifest['shared_ip'] = False
    else:
        manifest['shared_ip'] = bool(manifest['shared_ip'])

    # Check archive
    manifest['archive'] = list(manifest.get('archive', []))
    if manifest['archive'] is None:
        manifest['archive'] = []

    # Adds cell specific information to the loaded manifest.
    manifest['cell'] = context.GLOBAL.cell
    manifest['zookeeper'] = context.GLOBAL.zk.url

    _add_system_services(manifest)
    _add_features(manifest)

    manifest['host_ip'] = tm_env.host_ip

    if 'endpoints' not in manifest:
        manifest['endpoints'] = []

    if 'ephemeral_ports' not in manifest:
        manifest['ephemeral_ports'] = 0

    if 'passthrough' not in manifest:
        manifest['passthrough'] = []

    if 'vring' not in manifest:
        manifest['vring'] = {}
    if 'cells' not in manifest['vring']:
        manifest['vring']['cells'] = []
    if 'identity_group' not in manifest:
        manifest['identity_group'] = None
    if 'identity' not in manifest:
        manifest['identity'] = None

    return manifest


def _add_system_services(manifest):
    """Configure system services.

    Current system services:
     - sshd
    """
    if os.name == 'nt':
        # TODO: implement this
        return

    # Configures sshd services in the container.
    sshd_svc = {
        'name': 'sshd',
        'proid': None,
        'restart': {
            'limit': 5,
            'interval': 60,
        },
        'command': '%s -D -f /etc/ssh/sshd_config '
                   '-p $TREADMILL_ENDPOINT_SSH' % (subproc.resolve('sshd'))
    }
    manifest['system_services'].append(sshd_svc)

    ssh_endpoint = {
        'name': 'ssh',
        'port': 0,
        'type': 'infra',
    }
    manifest['endpoints'].append(ssh_endpoint)


def _add_features(manifest):
    """Configure optional container features."""
    if os.name == 'nt':
        # TODO: implement this
        return

    for feature in manifest.get('features', []):
        try:
            feature_mod = importlib.import_module(
                'treadmill.appmgr.features.' + feature
            )
            feature_mod.configure(manifest)
        except ImportError:
            _LOGGER.exception('Unable to load feature: %s', feature)
            raise Exception('Unsupported feature: ' + feature)
        except Exception:
            _LOGGER.exception('Error configuring feature: %s', feature)
            raise Exception('Error configuring feature: ' + feature)
