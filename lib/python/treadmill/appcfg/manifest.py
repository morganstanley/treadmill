"""Generation of Treadmill manifests from cell events.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import json
import logging
import os

from treadmill import appcfg
from treadmill import context
from treadmill import exc
from treadmill import subproc
from treadmill import supervisor
from treadmill import utils
from treadmill import yamlwrapper as yaml

from treadmill.appcfg import features

_LOGGER = logging.getLogger(__name__)

_SSHD_PORT = 22


def read(filename, file_format='json'):
    """Standard way of reading a manifest.
    """
    with io.open(filename) as f:
        if file_format == 'json':
            manifest = json.load(fp=f)
        else:
            manifest = yaml.load(stream=f)

    return manifest


def load(event):
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
    # pylint: disable=too-many-statements
    #
    # TODO: need better input validation / setting defaults process.
    name = os.path.basename(event)
    manifest = read(event, 'yaml')

    utils.validate(manifest, [('image', False, str)])
    app_type = appcfg.AppType.get_app_type(manifest.get('image'))

    schema = [
        ('proid', True, str),
        ('environment', True, str),
        ('services', app_type == appcfg.AppType.NATIVE, list),
        ('command', False, str),
        ('args', False, list),
        ('endpoints', False, list),
        ('environ', False, list),
        ('cpu', True, str),
        ('memory', True, str),
        ('disk', True, str),
        ('keytabs', False, list),
    ]

    utils.validate(manifest, schema)
    manifest['system_services'] = []
    manifest['name'] = name
    manifest['app'] = appcfg.appname_basename(name)
    manifest['type'] = app_type.value
    manifest['uniqueid'] = appcfg.gen_uniqueid(event)

    if manifest['environment'] not in ['dev', 'qa', 'uat', 'prod']:
        _LOGGER.warning(
            'Unrecognized environment: %s', manifest['environment']
        )
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

    def _set_default(attr, value, obj=None):
        """Set default manifest attribute if it is not present."""
        if obj is None:
            obj = manifest
        if attr not in obj:
            obj[attr] = value

    _set_default('command', None)
    _set_default('args', [])
    _set_default('environ', [])
    _set_default('endpoints', [])
    _set_default('passthrough', [])
    _set_default('services', [])
    _set_default('vring', {})
    _set_default('cells', [], manifest['vring'])
    _set_default('identity_group', None)
    _set_default('identity', None)
    _set_default('data_retention_timeout', None)
    _set_default('lease', None)
    _set_default('keytabs', [])

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
            manifest['ephemeral_ports']['tcp']
        )

    if 'udp' not in manifest['ephemeral_ports']:
        manifest['ephemeral_ports']['udp'] = 0
    else:
        manifest['ephemeral_ports']['udp'] = int(
            manifest['ephemeral_ports']['udp']
        )
    return manifest


def add_linux_system_services(tm_env, manifest):
    """Configure linux system services."""
    unique_name = appcfg.manifest_unique_name(manifest)
    container_svcdir = supervisor.open_service(
        os.path.join(
            tm_env.apps_dir,
            unique_name
        ),
        existing=False
    )
    container_data_dir = container_svcdir.data_dir

    if 'vring' in manifest:
        # Add the Vring daemon services
        for cell in manifest['vring']['cells']:
            vring = {
                'name': 'vring.%s' % cell,
                'proid': 'root',
                'restart': {
                    'limit': 5,
                    'interval': 60,
                },
                'command': (
                    'unset TREADMILL_ZOOKEEPER; '
                    'exec {treadmill}/bin/treadmill sproc'
                    ' --cell {cell}'
                    ' vring'
                    ' --approot {tm_root}'
                    ' {manifest}'
                ).format(
                    treadmill=subproc.resolve('treadmill'),
                    cell=cell,
                    tm_root=tm_env.root,
                    manifest=os.path.join(container_data_dir, 'state.json')
                ),
                'environ': [
                    {
                        'name': 'KRB5CCNAME',
                        'value': os.path.expandvars(
                            'FILE:${TREADMILL_HOST_TICKET}'
                        ),
                    },
                ],
                'config': None,
                'downed': False,
                'trace': False,
            }
            manifest['system_services'].append(vring)

    # Create ticket refresh and container/endpoint presence service
    register_presence = {
        'name': 'register',
        'proid': 'root',
        'restart': {
            'limit': 5,
            'interval': 60,
        },
        'command': (
            'exec {treadmill}/bin/treadmill sproc'
            ' --zookeeper {zkurl}'
            ' --cell {cell}'
            ' presence register'
            ' {manifest} {container_dir}'
        ).format(
            treadmill=subproc.resolve('treadmill'),
            zkurl=manifest['zookeeper'],
            cell=manifest['cell'],
            manifest=os.path.join(container_data_dir, 'state.json'),
            container_dir=container_data_dir
        ),
        'environ': [
            {
                'name': 'KRB5CCNAME',
                'value': os.path.expandvars(
                    'FILE:${TREADMILL_HOST_TICKET}'
                ),
            },
            {
                'name': 'TREADMILL_ALIASES_PATH',
                'value': os.getenv('TREADMILL_ALIASES_PATH'),
            },
        ],
        'config': None,
        'downed': False,
        'trace': False,
    }
    manifest['system_services'].append(register_presence)

    # Create container /etc/hosts manager service
    run_overlay = os.path.join(container_data_dir, 'overlay', 'run')
    etc_overlay = os.path.join(container_data_dir, 'overlay', 'etc')
    hostaliases = {
        'name': 'hostaliases',
        'proid': 'root',
        'restart': {
            'limit': 5,
            'interval': 60,
        },
        'command': (
            'exec {treadmill}/bin/treadmill sproc'
            ' --cell {cell}'
            ' host-aliases'
            ' --aliases-dir {aliases_dir}'
            ' {hosts_original} {hosts_container}'
        ).format(
            treadmill=subproc.resolve('treadmill'),
            cell=manifest['cell'],
            aliases_dir=os.path.join(
                run_overlay, 'host-aliases',
            ),
            hosts_original=os.path.join(
                '/', 'etc', 'hosts'
            ),
            hosts_container=os.path.join(
                etc_overlay, 'hosts'
            ),
        ),
        'environ': [],
        'downed': False,
        'trace': False,
    }
    manifest['system_services'].append(hostaliases)

    # Create the user app top level supervisor
    #
    # Reset environment variables set by treadmill to default values.
    start_container = {
        'name': 'start_container',
        'proid': 'root',
        'restart': {
            'limit': 0,
            'interval': 60,
        },
        'command': (
            'exec'
            ' {pid1} -i -m -p'
            ' --propagation slave'
            ' {treadmill}/bin/treadmill sproc'
            ' --cgroup /apps/{unique_name}/services'
            ' --cell {cell}'
            ' start-container'
            ' --container-root {container_dir}/root'
            ' {manifest}'
        ).format(
            treadmill=subproc.resolve('treadmill'),
            unique_name=unique_name,
            cell=manifest['cell'],
            pid1=subproc.resolve('pid1'),
            container_dir=container_data_dir,
            manifest=os.path.join(container_data_dir, 'state.json'),
        ),
        'environ': [],
        'config': None,
        'downed': True,
        'trace': False,
    }
    manifest['system_services'].append(start_container)


def add_linux_services(manifest):
    """Configure linux standard services."""
    # Configures sshd services in the container.
    sshd_svc = {
        'name': 'sshd',
        'proid': 'root',
        'restart': {
            'limit': 5,
            'interval': 60,
        },
        'command': (
            'exec {sshd} -D -f /etc/ssh/sshd_config'
            ' -p {sshd_port}'
        ).format(
            sshd=subproc.resolve('sshd'),
            sshd_port=_SSHD_PORT
        ),
        'root': True,
        'environ': [],
        'config': None,
        'downed': False,
        'trace': False,
    }
    manifest['services'].append(sshd_svc)

    ssh_endpoint = {
        'name': 'ssh',
        'proto': 'tcp',
        'port': _SSHD_PORT,
        'type': 'infra',
    }
    manifest['endpoints'].append(ssh_endpoint)


def add_manifest_features(manifest, runtime, tm_env):
    """Configure optional container features."""
    for feature in manifest.get('features', []):
        if not features.feature_exists(feature):
            _LOGGER.error('Unable to load feature: %s', feature)
            raise exc.ContainerSetupError(
                msg='Unsupported feature: {}'.format(feature),
                reason='feature',
            )

        feature_mod = features.get_feature(feature)(tm_env)

        if not feature_mod.applies(manifest, runtime):
            _LOGGER.error('Feature does not apply: %s', feature)
            raise exc.ContainerSetupError(
                msg='Unsupported feature: {}'.format(feature),
                reason='feature',
            )
        try:
            feature_mod.configure(manifest)
        except Exception:
            _LOGGER.exception('Error configuring feature: %s', feature)
            raise exc.ContainerSetupError(
                msg='Error configuring feature: {}'.format(feature),
                reason='feature',
            )
