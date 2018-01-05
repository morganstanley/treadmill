"""Prestash tickets on Treadmill masters.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os

import click

from treadmill import yamlwrapper as yaml


_KRB5_PRESTASH = '/ms/dist/aurora/bin/krb5_prestash'

_INFRA_FILE = '/ms/dist/cloud/PROJ/treadmill-tools/prod/etc/infra3.yml'


def _hosts(env, infrafile):
    """Returns list of hosts to prestash."""
    with io.open(infrafile) as f:
        infra = yaml.load(stream=f)
        ldap_servers = infra[env]['__default__']['ldap_servers']
        return [server['host'] for server in ldap_servers]


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--env', type=str, required=False, default='prod',
                  help='Treadmill environment.')
    @click.option('--infra', type=click.Path(exists=True),
                  default=_INFRA_FILE,
                  help='Infra file.')
    @click.argument('proid')
    def prestash(env, infra, proid):
        """Prestash tickets on a Treadmill admin servers."""
        masters = set()
        for host in _hosts(env, infra):
            masters.add(host)

        print('Prestash tickets for proid: %s' % proid)
        for hostname in masters:
            print('hostname: %s' % hostname)
            os.system('%s insert %s %s' % (_KRB5_PRESTASH, proid, hostname))

    return prestash
