"""
Unit test for treadmill.cli.allocation
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import click
import click.testing
import mock

import treadmill
from treadmill import plugin_manager


class AllocationTest(unittest.TestCase):
    """Mock test for treadmill.cli.allocation"""

    def setUp(self):
        """Setup common test variables"""
        self.runner = click.testing.CliRunner()
        self.alloc_cli = plugin_manager.load('treadmill.cli',
                                             'allocation').init()

    @mock.patch('treadmill.restclient.get')
    @mock.patch('treadmill.restclient.delete',
                mock.Mock(return_value=mock.MagicMock()))
    @mock.patch('treadmill.context.Context.admin_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_allocation_delete(self, get_mock):
        """Test cli.allocation: delete"""
        # delete a tenant
        # subtest case 1: no subtenant and reservation
        # initiate two returning objects from two restclient.get invocations
        return_mock1 = mock.Mock()
        return_mock2 = mock.Mock()
        # this one is for get all tenants
        return_mock1.json.return_value = [{
            '_id': None,
            'tenant': 'tent',
            'systems': [1, 2, 3]}]
        # this one is for get all reservations under 'tent'
        return_mock2.json.return_value = []
        get_mock.side_effect = [return_mock1, return_mock2]
        result = self.runner.invoke(self.alloc_cli,
                                    ['delete', 'tent'])
        self.assertEqual(result.exit_code, 0)
        treadmill.restclient.delete.assert_called_with(
            ['http://xxx:1234'],
            '/tenant/tent'
        )
        calls = [mock.call(['http://xxx:1234'], '/tenant/'),
                 mock.call(['http://xxx:1234'], '/allocation/tent')]
        get_mock.assert_has_calls(calls)
        self.assertEqual(treadmill.restclient.get.call_count, 2)

        # subtest case 2: has subtenant
        get_mock.reset_mock()
        get_mock.return_value = mock.DEFAULT
        get_mock.side_effect = None
        return_mock1.json.return_value = [
            {'_id': None,
             'tenant': 'tent',
             'systems': [1, 2, 3]},
            {'_id': None,
             'tenant': 'tent:subtent',
             'systems': [1, 2, 3]}]
        get_mock.return_value = return_mock1
        result = self.runner.invoke(self.alloc_cli,
                                    ['delete', 'tent'])
        self.assertEqual(result.exit_code, 0)
        get_mock.assert_called_once_with(['http://xxx:1234'], '/tenant/')

        # subtest case 3: tenant does not exist
        get_mock.reset_mock()
        get_mock.return_value = mock.DEFAULT
        from treadmill.restclient import NotFoundError
        get_mock.side_effect = [return_mock2, NotFoundError]
        result = self.runner.invoke(self.alloc_cli,
                                    ['delete', 'tent'])
        self.assertEqual(result.exit_code, 1)
        calls = [mock.call(['http://xxx:1234'], '/tenant/'),
                 mock.call(['http://xxx:1234'], '/allocation/tent')]
        get_mock.assert_has_calls(calls)
        self.assertEqual(treadmill.restclient.get.call_count, 2)

        # subtest case 4: has reservation
        get_mock.reset_mock()
        get_mock.return_value = mock.DEFAULT
        return_mock1.json.return_value = [
            {'_id': None,
             'tenant': 'tent',
             'systems': [1, 2, 3]}]
        return_mock2.json.return_value = [{'_id': 'tent/dev'}]
        get_mock.side_effect = [return_mock1, return_mock2]
        result = self.runner.invoke(self.alloc_cli,
                                    ['delete', 'tent'])
        self.assertEqual(result.exit_code, 0)
        calls = [mock.call(['http://xxx:1234'], '/tenant/'),
                 mock.call().json(),
                 mock.call(['http://xxx:1234'], '/allocation/tent')]
        get_mock.assert_has_calls(calls)
        self.assertEqual(treadmill.restclient.get.call_count, 2)

        # delete all reservations
        result = self.runner.invoke(self.alloc_cli,
                                    ['delete', 'tent/dev'])
        self.assertEqual(result.exit_code, 0)
        treadmill.restclient.delete.assert_called_with(
            ['http://xxx:1234'],
            '/allocation/tent/dev'
        )

        # delete a reservation
        result = self.runner.invoke(self.alloc_cli,
                                    ['delete', 'tent/dev/rr'])
        self.assertEqual(result.exit_code, 0)
        treadmill.restclient.delete.assert_called_with(
            ['http://xxx:1234'],
            '/allocation/tent/dev/reservation/rr'
        )

    @mock.patch('treadmill.restclient.put')
    @mock.patch('treadmill.restclient.get')
    @mock.patch('treadmill.context.Context.admin_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_allocation_configure(self, get_mock, put_mock):
        """Test cli.allocation: configure"""
        get_mock.return_value.json.return_value = {'systems': [1, 2]}
        self.runner.invoke(
            self.alloc_cli, ['configure', 'tent/dev', '--systems', '3']
        )
        put_mock.assert_called_with(
            [u'http://xxx:1234'],
            u'/tenant/tent/dev',
            payload={
                u'systems': [1, 2, 3]
            }
        )

        put_mock.reset_mock()
        self.runner.invoke(
            self.alloc_cli,
            ['configure', 'tent/dev', '--systems', '3', '--set']
        )
        put_mock.assert_called_with(
            [u'http://xxx:1234'],
            u'/tenant/tent/dev',
            payload={
                u'systems': [3]
            }
        )


if __name__ == '__main__':
    unittest.main()
