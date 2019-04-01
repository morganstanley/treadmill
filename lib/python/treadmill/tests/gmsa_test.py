"""Unit test for the treadmill_ms.Gmsa.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import mock

import ldap3

from treadmill import gmsa


class GmsaTest(unittest.TestCase):
    """ Tests for spn operations """

    @mock.patch('treadmill.ad._servers.create_ldap_connection', mock.Mock())
    def test_gmsa_query_spn(self):
        """Test Gmsa.query_spn
        """
        gmsa_ = gmsa.Gmsa('dc', 'search_base')

        gmsa_obj = {
            'dn': 'testdn1',
            'attributes': {
                'servicePrincipalName': ['SPN1', 'SPN2', 'SPN3']
            }
        }

        # pylint: disable=protected-access
        gmsa_._get_gmsa_obj = mock.MagicMock(return_value=gmsa_obj)
        try:
            result = gmsa_.query_spn('whateverproid')
            self.assertEqual(result, {
                'dn': 'testdn1',
                'spn': ['SPN1', 'SPN2', 'SPN3']
            })
        except RuntimeError:
            self.fail("Should not raise when spn query succeeds")

        # pylint: disable=protected-access
        gmsa_._get_gmsa_obj = mock.MagicMock(return_value=None)
        with self.assertRaises(RuntimeError):
            gmsa_.query_spn('whateverproid')

    @mock.patch('treadmill.ad._servers.create_ldap_connection', mock.Mock())
    def test_gmsa_add_spn(self):
        """Test Gmsa.query_spn
        """
        gmsa_ = gmsa.Gmsa('dc', 'search_base')

        # test SPN duplicate senario
        # pylint: disable=protected-access
        gmsa_._duplicate_spn = mock.MagicMock(return_value=True)
        with self.assertRaises(RuntimeError):
            gmsa_.add_spn('proid1', 'SPN1')

        # test gmsa not exist senario
        # pylint: disable=protected-access
        gmsa_._duplicate_spn = mock.MagicMock(return_value=False)
        # pylint: disable=protected-access
        gmsa_._get_gmsa_obj = mock.MagicMock(return_value=None)
        with self.assertRaises(RuntimeError):
            gmsa_.add_spn('proid1', 'SPN1')

        # test normal case
        # pylint: disable=protected-access
        gmsa._check_ldap3_operation = mock.MagicMock(return_value=True)
        # pylint: disable=protected-access
        gmsa_._duplicate_spn = mock.MagicMock(return_value=False)
        # pylint: disable=protected-access
        gmsa_._get_gmsa_obj = mock.MagicMock(return_value={'dn': 'gmsadn'})
        gmsa_.add_spn('proid1', 'SPN1')
        gmsa_.conn.modify.assert_called_with(
            'gmsadn',
            {'servicePrincipalName': [(ldap3.MODIFY_ADD, ['SPN1'])]}
        )

    @mock.patch('treadmill.ad._servers.create_ldap_connection', mock.Mock())
    def test_gmsa_delete_spn(self):
        """Test Gmsa.delete_spn
        """
        gmsa_ = gmsa.Gmsa('dc', 'search_base')

        # test gmsa not exist senario
        # pylint: disable=protected-access
        gmsa_._get_gmsa_obj = mock.MagicMock(return_value=None)
        with self.assertRaises(RuntimeError):
            gmsa_.delete_spn('proid1', 'SPN1')

        # test normal case
        # pylint: disable=protected-access
        gmsa._check_ldap3_operation = mock.MagicMock(return_value=True)
        # pylint: disable=protected-access
        gmsa_._get_gmsa_obj = mock.MagicMock(return_value={'dn': 'gmsadn'})
        gmsa_.delete_spn('proid1', 'SPN1')
        gmsa_.conn.modify.assert_called_with(
            'gmsadn',
            {'servicePrincipalName': [(ldap3.MODIFY_DELETE, ['SPN1'])]}
        )


if __name__ == '__main__':
    unittest.main()
