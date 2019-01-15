"""Unit test for treadmill.cli.allocation
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

    @mock.patch('treadmill.restclient.put')
    @mock.patch('treadmill.restclient.post')
    @mock.patch('treadmill.restclient.get')
    @mock.patch('treadmill.cli.allocation._display_tenant', mock.Mock())
    @mock.patch('treadmill.context.Context.admin_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_allocation_reserve(self, get_mock, post_mock, put_mock):
        """Test cli.allocation: reserve"""
        return_mock1 = mock.Mock()
        return_mock2 = mock.Mock()
        return_mock1.json.return_value = [{
            '_id': None,
            'tenant': 'tent',
            'systems': [1, 2, 3]}]
        return_mock2.json.return_value = {"cpu": "0%",
                                          "disk": "0M",
                                          "rank_adjustment": 10,
                                          "partition": "_default",
                                          "memory": "0M",
                                          "assignments": [],
                                          "rank": 100,
                                          "max_utilization": None,
                                          "_id": "tent/qa/test-v3",
                                          "cell": "test-v3",
                                          "traits": []}
        get_mock.side_effect = [return_mock1,
                                treadmill.restclient.NotFoundError,
                                return_mock1, return_mock2,
                                return_mock1, return_mock2]

        result = self.runner.invoke(
            self.alloc_cli, ['reserve', 'tent', '--env', 'qa',
                             '--cell', 'test-v3', '--empty'])

        self.assertEqual(result.exit_code, 0)

        result = self.runner.invoke(
            self.alloc_cli, ['reserve', 'tent', '--env', 'qa',
                             '--cell', 'test-v3', '--memory', '125M',
                             '--partition', 'aq7'])
        self.assertEqual(result.exit_code, 0)

        result = self.runner.invoke(
            self.alloc_cli, ['reserve', 'tent', '--env', 'qa',
                             '--cell', 'test-v3',
                             '--max-utilization', '10'])
        self.assertEqual(result.exit_code, 0)

        result = self.runner.invoke(
            self.alloc_cli, ['reserve', 'tent', '--env', 'qa',
                             '--cell', 'test-v3', '--traits', 'X,Y'])
        self.assertEqual(result.exit_code, 1)

        call1 = mock.call(['http://xxx:1234'], '/tenant/tent')
        call2 = mock.call(['http://xxx:1234'],
                          '/allocation/tent/qa/reservation/test-v3')
        calls = [call1, call2, call1, call2, call1, call2, call1]

        self.assertEqual(get_mock.call_count, 7)
        get_mock.assert_has_calls(calls, any_order=False)

        call1 = mock.call(['http://xxx:1234'], '/allocation/tent/qa',
                          payload={'environment': 'qa'})
        call2 = mock.call(['http://xxx:1234'],
                          '/allocation/tent/qa/reservation/test-v3',
                          payload={'memory': '0M', 'cpu': '0%', 'disk': '0M'})
        calls = [call1, call2, call1, call1]
        post_mock.assert_has_calls(calls, any_order=False)
        self.assertEqual(post_mock.call_count, 4)

        call1 = mock.call(['http://xxx:1234'],
                          '/allocation/tent/qa/reservation/' +
                          'test-v3',
                          payload={'memory': '125M',
                                   'partition': 'aq7',
                                   'cpu': '0%',
                                   'disk': '0M'})
        call2 = mock.call(['http://xxx:1234'],
                          '/allocation/tent/qa/reservation/' +
                          'test-v3',
                          payload={'memory': '0M',
                                   'partition': '_default',
                                   'cpu': '0%',
                                   'disk': '0M',
                                   'max_utilization': 10})
        calls = [call1, call2]
        self.assertEqual(put_mock.call_count, 2)
        put_mock.assert_has_calls(calls, any_order=False)


if __name__ == '__main__':
    unittest.main()
