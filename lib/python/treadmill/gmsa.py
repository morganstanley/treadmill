"""SPN operation helper module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys
import logging

import ldap3

from treadmill import utils
from treadmill.ad import _servers as servers

import treadmill.ldap3kerberos

sys.modules['ldap3.protocol.sasl.kerberos'] = treadmill.ldap3kerberos

_LOGGER = logging.getLogger(__name__)


def _check_ldap3_operation(conn):
    """Checks that the ldap3 operation succeeded/failed.

    :param conn:
        The `ldap3.Connection` that the operation was made.
    :return:
        `True` if the operation succeed; false otherwise
    """
    result_code = conn.result['result']
    if result_code in (0, 68):
        return True

    return False


class Gmsa:
    """Treadmill Spn Operation class.
    """

    def __init__(self, dc, gmsa_search_base):
        """ Initialization
            dc: Domain Controller Name
            gmsa_search_base: Search Base OU
        """
        self.conn = servers.create_ldap_connection(dc)
        self.gmsa_search_base = gmsa_search_base

    def _duplicate_spn(self, name):
        """Check if spn is already registered in another GMSA
        """
        self.conn.search(
            search_base=self.gmsa_search_base,
            search_filter='(&(servicePrincipalName={}))'.format(name),
            attributes=['servicePrincipalName']
        )

        if not _check_ldap3_operation(self.conn):
            raise RuntimeError(self.conn.result['description'])

        for res in self.conn.response:
            if res['type'] == 'searchResEntry':
                return True

        return False

    def _get_gmsa_obj(self, proid):
        """ search and return gmsa obj under `gmsa_search_base`
        """
        self.conn.search(
            search_base=self.gmsa_search_base,
            search_filter='(&(objectClass={})(samAccountName={}$))'.format(
                'msDS-GroupManagedServiceAccount', proid),
            attributes=['servicePrincipalName']
        )

        if not _check_ldap3_operation(self.conn):
            raise RuntimeError(self.conn.result['description'])

        for res in self.conn.response:
            if res['type'] == 'searchResEntry':
                return res

        return None

    def add_spn(self, proid, spn):
        """ Add spn to a GMSA
        """

        if not self._duplicate_spn(spn):
            gmsa_obj = self._get_gmsa_obj(proid)
            if gmsa_obj:
                self.conn.modify(
                    gmsa_obj['dn'],
                    {'servicePrincipalName': [(ldap3.MODIFY_ADD, [spn])]}
                )

                if not _check_ldap3_operation(self.conn):
                    raise RuntimeError(self.conn.result['description'])
            else:
                raise RuntimeError('Proid:{} not found'.format(proid))
        else:
            raise RuntimeError('Spn already added to another gmsa')

    def delete_spn(self, proid, spn):
        """ Remove spn to a GMSA
        """

        gmsa_obj = self._get_gmsa_obj(proid)
        if gmsa_obj:
            self.conn.modify(
                gmsa_obj['dn'],
                {'servicePrincipalName': [(ldap3.MODIFY_DELETE, [spn])]}
            )
            if not _check_ldap3_operation(self.conn):
                raise RuntimeError(self.conn.result['description'])
        else:
            raise RuntimeError('Proid:{} not found'.format(proid))

    def query_spn(self, proid):
        """ Return list of spn registered for a GMSA
        On success return a dict:
            {
                'dn': dn,
                'spn': [spn]
            }
        On failure throw exception
        """
        gmsa_obj = self._get_gmsa_obj(proid)
        if gmsa_obj:
            result = {
                'dn': gmsa_obj['dn'],
                'spn': []
            }
            if 'servicePrincipalName' in gmsa_obj['attributes']:
                result['spn'].extend(
                    utils.get_iterable(
                        gmsa_obj['attributes']['servicePrincipalName']
                    )
                )

            return result
        else:
            raise RuntimeError('GMSA \'{}\' not found'.format(proid))
