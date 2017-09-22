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

import treadmill
from treadmill import appcfg
from treadmill import context
from treadmill import subproc
from treadmill import supervisor
from treadmill import utils
from treadmill import yamlwrapper as yaml

from treadmill.appcfg import features


_LOGGER = logging.getLogger(__name__)


def read(filename, file_format='json'):
    """Standard way of reading a manifest.
    """
    with io.open(filename) as f:
        if file_format == 'json':
            manifest = json.load(fp=f)
        else:
            manifest = yaml.load(stream=f)

    return manifest


def load(tm_env, event, runtime):
    """Loads the app event file, ensuring it is in valid format, and supplement
    it into a full Treadmill manifest.

    :param tm_env:
        Full path to the application node event in the zookeeper cache.
     :type event:
        ``treadmill.appenv.AppEnvironment``
    :param event:
        Full path to the application node event in the zookeeper cache.
    :type event:
        ``str``
    :param runtime:
        The name of the runtime to use.
    :type runtime:
        ``str``
    :return:
        Application manifest object
    :rtype:
        ``dict``
    """
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

    _add_runtime(tm_env, manifest, runtime)
    _add_features(manifest, runtime)

    return manifest


def _add_runtime(tm_env, manifest, runtime):
    """Adds runtime specific details to the manifest."""
    if runtime == 'linux':
        _add_runtime_linux(tm_env, manifest)


def _add_runtime_linux(tm_env, manifest):
    """Adds linux runtime specific details to the manifest."""
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
            'proid': (
                'root' if service.get('root', False)
                else manifest['proid']
            ),
            'environ': manifest['environ'],
            'config': None,
            'downed': False,
            'trace': True,
        }
        for service in manifest.get('services', [])
    ]

    _add_linux_system_services(tm_env, manifest)
    _add_linux_services(manifest)


def _add_linux_system_services(tm_env, manifest):
    """Configure linux system services."""
    container_svcdir = supervisor.open_service(
        os.path.join(
            tm_env.apps_dir,
            appcfg.manifest_unique_name(manifest)
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
                    'exec {tm} sproc'
                    ' --zookeeper {zkurl}'
                    ' --cell {cell}'
                    ' vring'
                    ' --approot {tm_root}'
                    ' {manifest}'
                ).format(
                    tm=treadmill.TREADMILL_BIN,
                    zkurl=manifest['zookeeper'],
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
            'exec {tm} sproc'
            ' --zookeeper {zkurl}'
            ' --cell {cell}'
            ' presence register'
            ' --approot {tm_root}'
            ' {manifest} {container_dir}'
        ).format(
            tm=treadmill.TREADMILL_BIN,
            zkurl=manifest['zookeeper'],
            cell=manifest['cell'],
            tm_root=tm_env.root,
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
    etc_overlay = os.path.join(container_data_dir, 'overlay', 'etc')
    hostaliases = {
        'name': 'hostaliases',
        'proid': 'root',
        'restart': {
            'limit': 5,
            'interval': 60,
        },
        'command': (
            'exec {tm} sproc'
            ' --cell {cell}'
            ' host-aliases'
            ' --aliases-dir {aliases_dir}'
            ' {hosts_original} {hosts_container}'
        ).format(
            tm=treadmill.TREADMILL_BIN,
            cell=manifest['cell'],
            aliases_dir=os.path.join(etc_overlay, 'host-aliases'),
            hosts_original=os.path.join(etc_overlay, 'hosts.original'),
            hosts_container=os.path.join(etc_overlay, 'hosts'),
        ),
        'environ': [],
        'downed': False,
        'trace': False,
    }
    manifest['system_services'].append(hostaliases)

    # Create the user app top level supervisor
    start_container = {
        'name': 'start_container',
        'proid': 'root',
        'restart': {
            'limit': 1,
            'interval': 60,
        },
        'command': (
            'exec {chroot} {container_dir}/root'
            ' {pid1} -m -p -i'
            ' {svscan} -s /services'
        ).format(
            chroot=subproc.resolve('chroot'),
            container_dir=container_data_dir,
            pid1=subproc.resolve('pid1'),
            svscan=subproc.resolve('s6_svscan'),
        ),
        'environ': [],
        'config': None,
        'downed': True,
        'trace': False,
    }
    manifest['system_services'].append(start_container)

    # Create the services monitor service
    monitor = {
        'name': 'monitor',
        'proid': 'root',
        'restart': {
            'limit': 5,
            'interval': 60,
        },
        'command': (
            'exec {tm} sproc'
            ' --cell {cell}'
            ' monitor services'
            ' --approot {tm_root}'
            ' -c {container_dir}'
            ' -s {services_opts}'
        ).format(
            tm=treadmill.TREADMILL_BIN,
            cell=manifest['cell'],
            tm_root=tm_env.root,
            container_dir=container_svcdir.directory,
            # This adds all services beside monitor itself
            services_opts=' -s'.join(
                [
                    os.path.join(container_data_dir, 'sys', s['name'])
                    for s in manifest['system_services']
                ] +
                [
                    os.path.join(container_data_dir, 'services', s['name'])
                    for s in manifest['services']
                ]
            )
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
    manifest['system_services'].append(monitor)


def _add_linux_services(manifest):
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
            ' -p $TREADMILL_ENDPOINT_SSH'
        ).format(
            sshd=subproc.resolve('sshd')
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
        'port': 0,
        'type': 'infra',
    }
    manifest['endpoints'].append(ssh_endpoint)


def _add_features(manifest, runtime):
    """Configure optional container features."""
    for feature in manifest.get('features', []):
        feature_mod = features.get_feature(feature)()

        if feature_mod is None:
            _LOGGER.error('Unable to load feature: %s', feature)
            raise Exception('Unsupported feature: ' + feature)

        if not feature_mod.applies(manifest, runtime):
            _LOGGER.error('Feature does not apply: %s', feature)
            raise Exception('Unsupported feature: ' + feature)

        try:

            feature_mod.configure(manifest)
        except Exception:
            _LOGGER.exception('Error configuring feature: %s', feature)
            raise Exception('Error configuring feature: ' + feature)
