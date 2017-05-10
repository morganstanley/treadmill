"""Generation of Treadmill manifests from cell events."""


import logging
import os

import yaml

from treadmill import appcfg
from treadmill import context
from treadmill import osnoop
from treadmill import utils
from treadmill import subproc

from treadmill.appcfg import features


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

    :param tm_env:
        Full path to the application node event in the zookeeper cache.
     :type event:
        ``treadmill.appenv.App``
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

    utils.validate(manifest, [('image', False, str)])
    app_type = appcfg.AppType.get_app_type(manifest.get('image'))

    schema = [
        ('proid', True, str),
        ('environment', True, str),
        ('services', app_type != appcfg.AppType.DOCKER, list),
        ('endpoints', False, list),
        ('environ', False, list),
        ('entry_point', False, str),
        ('cpu', True, str),
        ('memory', True, str),
        ('disk', True, str),
    ]
    utils.validate(manifest, schema)
    manifest['system_services'] = []
    manifest['name'] = name
    manifest['app'] = appcfg.appname_basename(name)
    manifest['type'] = app_type.value
    manifest['uniqueid'] = appcfg.gen_uniqueid(event)

    if manifest['environment'] not in ['dev', 'qa', 'uat', 'prod']:
        _LOGGER.warn('Unrecognized environment: %s', manifest['environment'])
        raise Exception('Invalid environment: ' + manifest['environment'])

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

    _add_ssh_system_service(manifest)
    _add_features(manifest)

    manifest['host_ip'] = tm_env.host_ip

    def _set_default(attr, value, obj=None):
        """Set default manifest attribute if it is not present."""
        if obj is None:
            obj = manifest
        if attr not in obj:
            obj[attr] = value

    _set_default('environ', [])
    _set_default('passthrough', [])
    _set_default('vring', {})
    _set_default('cells', [], manifest['vring'])
    _set_default('identity_group', None)
    _set_default('identity', None)
    _set_default('data_retention_timeout', None)

    # Normalize restart count
    manifest['services'] = [
        {
            'name': service['name'],
            'command': service['command'],
            'restart': {
                'limit': int(service['restart']['limit']),
                'interval': int(service['restart']['interval']),
            },
            'root': service.get('root', False),
        }
        for service in manifest.get('services', [])
    ]
    # Normalize optional and port information
    manifest['endpoints'] = [
        {
            'name': endpoint['name'],
            'port': int(endpoint['port']),
            'type': endpoint.get('type', None),
            'proto': endpoint.get('proto', 'tcp'),
        }
        for endpoint in manifest.get('endpoints', [])
    ]

    # TODO: need better way to normalize.
    if 'ephemeral_ports' not in manifest:
        manifest['ephemeral_ports'] = {'tcp': 0, 'udp': 0}

    if 'tcp' not in manifest['ephemeral_ports']:
        manifest['ephemeral_ports']['tcp'] = 0
    else:
        manifest['ephemeral_ports']['tcp'] = int(
            manifest['ephemeral_ports']['tcp'])

    if 'udp' not in manifest['ephemeral_ports']:
        manifest['ephemeral_ports']['udp'] = 0
    else:
        manifest['ephemeral_ports']['udp'] = int(
            manifest['ephemeral_ports']['udp'])

    return manifest


@osnoop.windows
def _add_ssh_system_service(manifest):
    """Configures sshd services in the container."""
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
    for feature in manifest.get('features', []):
        feature_mod = features.get_feature(feature)

        if feature_mod is None:
            _LOGGER.error('Unable to load feature: %s', feature)
            raise Exception('Unsupported feature: ' + feature)

        if not feature_mod.applies(manifest):
            _LOGGER.error('Feature does not apply: %s', feature)
            raise Exception('Unsupported feature: ' + feature)

        try:

            feature_mod.configure(manifest)
        except Exception:
            _LOGGER.exception('Error configuring feature: %s', feature)
            raise Exception('Error configuring feature: ' + feature)
