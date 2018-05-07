"""Unit test for treadmill.api input validation.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

# Disable R0915: Too many statements
# pylint: disable=R0915

import copy
import unittest

import jsonschema
import jsonpointer
import mock

from treadmill import schema
from treadmill.api import allocation
from treadmill.api import app
from treadmill.api import app_monitor
from treadmill.api import app_group
from treadmill.api import cell
from treadmill.api import server
from treadmill.api import tenant
from treadmill.api import instance


def _ok(func, *args, **kwargs):
    """Tests that function arguments pass validation."""
    func(*args, **kwargs)


def _fail(func, *args, **kwargs):
    """Tests that function arguments do not pass validation."""
    try:
        func(*args, **kwargs)
        failed = False
    except jsonschema.exceptions.ValidationError:
        failed = True
    assert failed, 'validation error expected.'


def _patch(obj, jsonptr, value):
    """Returns patched object."""
    return jsonpointer.set_pointer(obj, jsonptr, value, inplace=False)


def _without(obj, attrs, path=None):
    """Returns patched object with attributes deleted."""
    if path:
        ptrval = copy.deepcopy(jsonpointer.resolve_pointer(obj, path))
        return _patch(obj, path, _without(ptrval, attrs))
    else:
        updated = copy.deepcopy(obj)
        for attr in attrs:
            if attr in updated:
                del updated[attr]
        return updated


class ApiSchemaTest(unittest.TestCase):
    """treadmill.schema tests."""

    def setUp(self):
        schema._TEST_MODE = True  # pylint: disable=W0212

    def tearDown(self):
        # Access to a protected member of a client class
        # pylint: disable=W0212

        schema._TEST_MODE = False

    def test_helpers(self):
        """Test helper methods."""
        self.assertEqual({'a': 1}, _patch({'a': 2}, '/a', 1))
        self.assertEqual({}, _without({'a': 2}, ['a']))
        self.assertEqual(
            {'a': [{}]},
            _without({'a': [{'a': 1}]}, ['a'], path='/a/0')
        )

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=None))
    def test_app_get(self):
        """Test input validation for app.get."""
        api = app.API()

        _ok(api.get, 'foo.bla')
        _ok(api.get, 'foo.bla.bar')
        _ok(api.get, 'foo.bla.123_-')

        _fail(api.get, 1)
        _fail(api.get, 'aaa,aaa')
        _fail(api.get, 'aaa/aaa')
        _fail(api.get, 'aaa#aaa')

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=None))
    def test_app_create(self):
        """Test input validation for app.create."""
        api = app.API()

        good = {
            'memory': '1G',
            'cpu': '100%',
            'disk': '1G',
            'services': []
        }
        _fail(api.create, 'foo.bla', good)
        _fail(api.create, 'foo@treadmll-users.bla', good)

        _fail(api.create, 'foo.bla', _patch(good, '/memory', 1))
        _fail(api.create, 'foo.bla', _patch(good, '/disk', 1))
        _fail(api.create, 'foo.bla', _patch(good, '/cpu', 1))
        _fail(api.create, 'foo.bla', _without(good, ['services']))

        # Validate service name.
        good.update({'services': [
            {'name': 'sleep', 'command': '/bin/sleep 1'}
        ]})
        _ok(api.create, 'foo.bla', good)
        _ok(api.create, 'foo-bar.bla', good)
        _ok(api.create, 'foo@treadmll-users.bla', good)

        _fail(api.create, 'foo.bla',
              _patch(good, '/services/0/name', 1))
        _fail(api.create, 'foo.bla',
              _patch(good, '/services/0/name', 'sss/ddd'))
        _fail(api.create, 'foo.bla',
              _patch(good, '/services/0/name', 's' * 61))

        # Validate service restart rate.
        _ok(api.create, 'foo.bla',
            _patch(good, '/services/0/restart', {'limit': 0}))
        _ok(api.create, 'foo.bla',
            _patch(good, '/services/0/restart', {'limit': 0, 'interval': 60}))
        _fail(api.create, 'foo.bla',
              _patch(good, '/services/0/restart', {'limit': 11}))
        _fail(api.create, 'foo.bla',
              _patch(good, '/services/0/restart',
                     {'limit': 10, 'interval': 3000}))
        _fail(api.create, 'foo.bla',
              _patch(good, '/services/0/invalid_attribute', '1'))

        # Command line can be anything.
        _ok(api.create, 'foo.bla',
            _patch(good, '/services/0/command', '123^%!$@#' * 100))

        # Endpoints
        good.update({'endpoints': [
            {'name': 'http', 'port': 8080}
        ]})
        _ok(api.create, 'foo.bla', good)
        _ok(api.create, 'foo.bla',
            _patch(good, '/endpoints/0/proto', 'udp'))
        _ok(api.create, 'foo.bla',
            _patch(good, '/endpoints/0/proto', 'tcp'))
        _fail(api.create, 'foo.bla',
              _patch(good, '/endpoints/0/proto', 'tcp, udp'))
        _fail(api.create, 'foo.bla',
              _patch(good, '/endpoints/0/name', 'sss:d'))
        _fail(api.create, 'foo.bla',
              _patch(good, '/endpoints/0/port', '1234'))

        # Environ
        good.update({'environ': [
            {'name': 'XXX', 'value': 'YYY'}
        ]})
        _ok(api.create, 'foo.bla', good)
        _fail(api.create, 'foo.bla',
              _patch(good, '/environ/0/name', 1))

        # Tickets.
        good.update({'tickets': ['myproid@krb.realm']})
        good.update({'tickets': ['myproid-foo@krb.realm']})
        _ok(api.create, 'foo.bla', good)
        _fail(api.create, 'foo.bla',
              _patch(good, '/tickets/0', 'ddd:d'))

        # Features
        good.update({'features': ['foo']})
        _ok(api.create, 'foo.bla', good)
        _ok(api.create, 'foo.bla',
            _patch(good, '/features/0', 'foo_bar'))
        _ok(api.create, 'foo.bla',
            _patch(good, '/features/0', 'foo-bar'))
        _fail(api.create, 'foo.bla',
              _patch(good, '/features/0', 'foo:'))

        # Shared ip/network.
        good.update({'shared_ip': True, 'shared_network': False})
        _ok(api.create, 'foo.bla', good)
        _fail(api.create, 'foo.bla', _patch(good, '/shared_ip', 1))
        _fail(api.create, 'foo.bla', _patch(good, '/shared_network', 0))

        # passthrough
        good.update({'passthrough': ['xxx.xx.com', '123.123.123.123']})
        _ok(api.create, 'foo.bla', good)
        _fail(api.create, 'foo.bla', _patch(good, '/passthrough/0', 1))
        # FIXME(boysson) _fail(api.create, 'foo.bla',
        #                      _patch(good, '/passthrough/0', '@.example.com'))

        # archive
        good.update({'archive': ['/var/tmp', 'xxx/*.log']})
        _ok(api.create, 'foo.bla', good)
        _fail(api.create, 'foo.bla', _patch(good, '/archive/0', 1))
        _fail(api.create, 'foo.bla', _patch(good, '/archive', 'aaa'))

        # vring.
        good.update({'vring': {
            'cells': ['aaa-001', 'bbb-001'],
            'rules': [{
                'endpoints': ['a', 'b', 'c'],
                'pattern': 'myproid.myapp.*',
            }]
        }})
        _ok(api.create, 'foo.bla', good)
        # Empty cell list ok, assume current cell.
        _ok(api.create, 'foo.bla', _patch(good, '/vring/cells', []))
        # At lest one endpoint must be specified.
        _fail(api.create, 'foo.bla',
              _patch(good, '/vring/rules/0/endpoints', []))
        _fail(api.create, 'foo.bla',
              _without(good, ['endpoints'], path='/vring/rules/0'))

        _ok(api.create, 'foo.bla', good)
        _ok(api.create, 'foo.bla', _patch(good, '/identity_group', 'bar.baz'))
        _fail(api.create, 'foo.bla', _patch(good, '/identity_group', 'bar'))

        # affinity_limits
        good.update({'affinity_limits': {}})
        _ok(api.create, 'foo.bla', good)
        _ok(api.create, 'foo.bla', _patch(good, '/affinity_limits/rack', 2))
        _ok(api.create, 'foo.bla',
            _patch(_patch(good,
                          '/affinity_limits/rack',
                          2),
                   '/affinity_limits/pod', 4))
        _fail(api.create, 'foo.bla', _patch(good, '/affinity_limits/rack', 0))
        _fail(api.create, 'foo.bla', _patch(good,
                                            '/affinity_limits/rack',
                                            'foo'))
        _fail(api.create, 'foo.bla', _patch(good, '/affinity_limits/foo', 1))

        # Data retention.
        _ok(api.create, 'f.b', _patch(good, '/data_retention_timeout', '1s'))
        _ok(api.create, 'f.b', _patch(good, '/data_retention_timeout', '12m'))
        _ok(api.create, 'f.b', _patch(good, '/data_retention_timeout', '12h'))
        _ok(api.create, 'f.b', _patch(good, '/data_retention_timeout', '12d'))
        _ok(api.create, 'f.b', _patch(good, '/data_retention_timeout', '12m'))
        _ok(api.create, 'f.b', _patch(good, '/data_retention_timeout', '12y'))
        _fail(api.create, 'f.b', _patch(good, '/data_retention_timeout', 12))
        _fail(api.create, 'f.b', _patch(good, '/data_retention_timeout', 'm'))

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=None))
    def test_server_create(self):
        """Test input validation for app.create."""

        api = server.API()

        good = {}

        _ok(api.create, 'xxx.xx.com', good)
        # FIXME(boysson) _fail(api.create, 'x(xx.xx.com', good)

        good.update({'partition': None})
        _ok(api.create, 'xxx.xx.com', good)

        good.update({'partition': 'xxx'})
        _ok(api.create, 'xxx.xx.com', good)
        _fail(api.create, 'xxx.xx.com', _patch(good, '/partition', 1))

        good.update({'cell': 'my-001-cell'})
        _ok(api.create, 'xxx.xx.com', good)
        _fail(api.create, 'xxx.xx.com', _patch(good, '/cell', 'wer()'))

        good.update({'parameters': ['volume=/xxx']})
        _ok(api.create, 'xxx.xx.com', good)
        _fail(api.create, 'xxx.xx.com', _patch(good, '/parameters/0', 's'))

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=None))
    def test_server_list(self):
        """Test server list input validation."""
        api = server.API()

        _ok(api.list, None, None)
        _ok(api.list, 'my-001-cell', None)
        _ok(api.list, 'my-001-cell', 'ccc')

        _fail(api.list, 'my-(001-cell', None)
        _fail(api.list, 'my-001-cell', 'x' * 33)

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=None))
    def test_cell(self):
        """Test cell input validation."""
        api = cell.API()

        good = {
            'treadmillid': 'treadmlx',
            'version': 'devel',
            'location': 'ny'
        }
        _ok(api.create, 'ny-001-cell', good)
        _fail(api.create, 'ny-001-cell', _without(good, ['version']))
        _fail(api.create, 'ny-001-cell', _without(good, ['treadmillid']))
        _fail(api.create, 'ny-001-cell', _without(good, ['location']))

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=None))
    def test_tenant(self):
        """Test tenant input validation."""
        api = tenant.API()

        good = {
            'systems': [1234, 2345]
        }
        _ok(api.create, 'aaa', good)
        _ok(api.create, 'www_', good)
        # is reserved.
        _fail(api.create, 'www-s', good)
        _ok(api.create, 'aaa:bbb', good)
        _fail(api.create, 'aaa::bbb', good)
        _fail(api.create, 'aaa:bbb:', good)
        _fail(api.create, 'aaa:bbb', _patch(good, '/systems/0', 'a'))

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=None))
    def test_allocation(self):
        """Test allocation input validation."""
        api = allocation.API()
        good = {
            'environment': 'prod'
        }
        _ok(api.create, 'aaa/prod', good)

        _ok(api.create, 'aaa/prod', _patch(good, '/environment', 'qa'))
        _ok(api.create, 'aaa/prod', _patch(good, '/environment', 'dev'))
        _ok(api.create, 'aaa/prod', _patch(good, '/environment', 'uat'))
        _fail(api.create, 'aaa/prod', _patch(good, '/environment', 'x'))
        _fail(api.create, 'aaa/prod', _patch(good, '/environment', ' uat '))

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=None))
    def test_reservation(self):
        """Test allocation input validation."""
        api = allocation.API().reservation

        good = {
            'memory': '1G',
            'cpu': '100%',
            'disk': '1G',
            'partition': 'xxx',
        }
        _ok(api.create, 'aaa/prod/cell', good)

        # Update
        good = {'cpu': '77%'}
        _fail(api.update, 'aaa/prod/cell', good)

        good['memory'] = '2G'
        good['disk'] = '1G'
        good['partition'] = 'yyy'

        _ok(api.update, 'aaa/prod/cell', good)
        _fail(api.update, 'aaa/prod/cell', _patch(good, '/environment', 'qa'))

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=None))
    def test_instance_create(self):
        """Test input validation for instance.create."""
        api = instance.API()

        good = {}
        _ok(api.create, 'foo.bla', good)
        _ok(api.create, 'foo@treadmill-users.bla', good)

        _ok(api.create, 'foo.bla', _patch(good, '/memory', '100M'))
        _fail(api.update, 'foo.bla', _patch(good, '/memory', '100M'))

        good = {
            'priority': 0
        }
        _ok(api.update, 'foo.bla#123456', good)
        _fail(api.update, 'foo.bla#123456', _patch(good, '/priority', -1))
        _fail(api.update, 'foo.bla#123456', _patch(good, '/memory', '100M'))

        # Features
        good = {
            'features': ['foo']
        }
        _ok(api.create, 'foo.bla', good)
        _ok(api.create, 'foo.bla',
            _patch(good, '/features/0', 'foo_bar'))
        _ok(api.create, 'foo.bla',
            _patch(good, '/features/0', 'foo-bar'))
        _fail(api.create, 'foo.bla',
              _patch(good, '/features/0', 'foo:'))

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=None))
    def test_app_group_get(self):
        """Test input validation for app_group.get."""
        api = app_group.API()

        _ok(api.get, 'foo.bla')
        _ok(api.get, 'foo.bla.bar')
        _ok(api.get, 'foo.bla.123_-')

        _fail(api.get, 1)
        _fail(api.get, 'aaa,aaa')
        _fail(api.get, 'aaa/aaa')
        _fail(api.get, 'aaa#aaa')

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=None))
    def test_app_group_create(self):
        """Test input validation for app_group.get."""
        api = app_group.API()

        good = {
            'group-type': 'dns',
            'cells': ['test', 'foo'],
            'data': [
                'foo=bar',
                'baz=flo'
            ]
        }
        _ok(api.create, 'foo.bla', good)

        _fail(api.create, 'foo.bla', _patch(good, '/memory', 1))
        _fail(api.create, 'foo.bla', _patch(good, '/data', ['key']))
        _fail(api.create, 'foo.bla', _patch(good, '/cell', ['+++']))

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=None))
    def test_appmonitor(self):
        """Test app_monitor input validation."""
        api = app_monitor.API()

        _ok(api.get, 'foo.bar')
        _ok(api.get, 'foo@mailgroup.xxx')

        good = {
            'count': 123
        }
        _ok(api.create, 'foo.bla', good)
        _ok(api.create, 'foo.bla', _patch(good, '/count', 0))
        _ok(api.create, 'foo.bla', _patch(good, '/count', 1000))

        _fail(api.create, 'foo.bla', _patch(good, '/count', -1))
        _fail(api.create, 'foo.bla', _patch(good, '/count', 1001))
        _fail(api.create, 'foo.bla', _patch(good, '/count', '1'))


if __name__ == '__main__':
    unittest.main()
