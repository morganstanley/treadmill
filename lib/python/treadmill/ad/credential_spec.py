"""Generates credential spec files for docker runtime on Windows.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import uuid

import docker
# Pylint warning unable to import because it is on Windows only
import win32security  # pylint: disable=E0401

from treadmill import fs
from treadmill import utils


_CREDENTIAL_SPECS_PATH = 'CredentialSpecs'


def _get_path(client):
    """Gets the credential spec path.
    """
    if client is None:
        client = docker.from_env()

    info = client.info()
    return os.path.join(info['DockerRootDir'], _CREDENTIAL_SPECS_PATH)


def generate(proid, name, client=None):
    """Generates a credential spec file for the given GMSA proid and returns
    the path to the file.
    """
    credential_specs_path = _get_path(client)

    dc_name = win32security.DsGetDcName()
    account_name = win32security.LookupAccountName(None, dc_name['DomainName'])

    dns_name = dc_name['DomainName']
    net_bios_name = account_name[1]
    sid = win32security.ConvertSidToStringSid(account_name[0])
    guid = str(uuid.UUID(str(dc_name['DomainGuid'])))

    doc = {
        'CmsPlugins': ['ActiveDirectory'],
        'DomainJoinConfig': {
            'Sid': sid,
            'MachineAccountName': proid,
            'Guid': guid,
            'DnsTreeName': dns_name,
            'DnsName': dns_name,
            'NetBiosName': net_bios_name
        },
        'ActiveDirectoryConfig': {
            'GroupManagedServiceAccounts': [
                {
                    'Name': proid,
                    'Scope': dns_name
                },
                {
                    'Name': proid,
                    'Scope': net_bios_name
                }
            ]
        }
    }

    path = os.path.join(credential_specs_path, name + '.json')
    with io.open(path, 'w') as f:
        f.writelines(utils.json_genencode(doc, indent=4))

    return 'file://{}.json'.format(name)


def cleanup(name, client=None):
    """Cleans up the credential spec file left behind.
    """
    credential_specs_path = _get_path(client)
    path = os.path.join(credential_specs_path, name + '.json')
    fs.rm_safe(path)
