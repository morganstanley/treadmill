"""Configures warpgate inside the container."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from treadmill import cellconfig
from treadmill.appcfg.features import feature_base


_LOGGER = logging.getLogger(__name__)


class WarpgateFeature(feature_base.Feature):
    """Feature to enable warpgate daemon in container
    """
    __slots__ = (
        '_servers',
        '_principal',
    )

    def __init__(self, tm_env):
        super().__init__(tm_env)
        (servers, principal) = self._get_warpgate_config()
        self._servers = servers
        self._principal = principal

    def applies(self, manifest, runtime):
        return (
            runtime == 'linux' and
            self._servers and
            len(manifest.get('tickets', [])) and
            any([env for env in manifest.get('environ', [])
                 if env['name'] == 'WARPGATE_POLICY'])
        )

    def configure(self, manifest):
        _LOGGER.info('Configuring warpgate.')

        # TODO: workaround to get policy from WARPGATE_POLICY env variable
        policy = None
        for environ in manifest['environ']:
            if environ['name'] == 'WARPGATE_POLICY':
                policy = environ['value']
                break

        manifest['services'].append(
            _generate_warpgate_service(
                account=manifest['tickets'][0],
                servers=self._servers,
                service_principal=self._principal,
                policy=policy,
            )
        )
        manifest['warpgate'] = True

    def _get_warpgate_config(self):
        """Read the WarpGate config from the cell data.
        """
        cell_config = cellconfig.CellConfig(self._tm_env.root)
        warpgate_cfg = cell_config.data['warpgate']
        servers = warpgate_cfg.get('servers', [])
        principal = warpgate_cfg.get('principal', 'host')
        return (servers, principal)


def _generate_warpgate_service(account, servers, service_principal, policy):
    cmd = (
        'exec $TREADMILL/bin/treadmill sproc'
        ' --logging-conf daemon_container.json'
        ' warpgate'
        ' --policy-servers {warpgates}'
        ' --policy {policy}'
        ' --service-principal {service_principal}'
        ' --tun-dev {tun_devname}'
        ' --tun-addr {tun_ipaddr}'
    ).format(
        warpgates=','.join(servers),
        service_principal=service_principal,
        policy=policy,
        tun_devname='eth0',
        tun_ipaddr='${TREADMILL_CONTAINER_IP}'
    )

    return {
        'name': 'warpgate',
        'proid': 'root',
        'restart': {
            'limit': 5,
            'interval': 60,
        },
        'command': cmd,
        'root': True,
        'environ': [
            {
                'name': 'KRB5CCNAME',
                'value': 'FILE:/var/spool/tickets/{principal}'.format(
                    principal=account
                ),
            },
        ],
        'config': None,
        'downed': False,
        'trace': False,
    }
