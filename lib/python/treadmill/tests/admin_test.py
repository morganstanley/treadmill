"""Unit test for treadmill admin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import unittest

import ldap3
import mock
import six

import treadmill
from treadmill.admin import _ldap as admin

# Disable wrong import order warning.
import treadmill.tests.treadmill_ldap_patch  # pylint: disable=C0411
treadmill.tests.treadmill_ldap_patch.monkey_patch()


# pylint: disable=too-many-lines

class AdminTest(unittest.TestCase):
    """Tests supervisor routines."""

    def test_and_query(self):
        """Test."""
        query = admin.AndQuery('a', 1)
        self.assertEqual('(a=1)', str(query))

        query('b', '*')
        self.assertEqual('(&(a=1)(b=*))', str(query))

    def test_entry_to_dict(self):
        """Test entry to dict conversion."""
        # Disable W0212: Test access protected members of admin module.
        # pylint: disable=W0212
        schema = [
            ('a', 'a', str),
            ('b', 'b', [str]),
            ('c', 'C', int),
            ('d', 'd', dict),
            ('e', 'e', bool),
            ('f', 'f', bool),
        ]

        self.assertEqual(
            admin._entry_2_dict(
                {
                    'a': ['1'],
                    'b': ['x'],
                    'c': ['1'],
                    'e': [True],
                    'f': [False],
                },
                schema
            ),
            {
                'a': '1',
                'b': ['x'],
                'C': 1,
                'e': True,
                'f': False
            },
        )
        self.assertEqual(
            admin._entry_2_dict(
                {
                    'a': ['1'],
                    'b': ['x'],
                    'd': ['{"x": 1}'],
                    # XXX: This is necessary until previous bad entries are
                    #      cleaned up.
                    'e': ['True'],
                    'f': ['1'],
                },
                schema
            ),
            {
                'a': '1',
                'b': ['x'],
                'd': {
                    'x': 1
                },
                'e': True,
                'f': True,
            }
        )
        self.assertEqual(
            admin._dict_2_entry(
                {
                    'a': '1',
                    'b': ['x'],
                    'C': 1,
                    'e': False,
                    'f': True
                },
                schema
            ),
            {
                'a': ['1'],
                'b': ['x'],
                'c': ['1'],
                'e': [False],
                'f': [True],
            }
        )
        self.assertEqual(
            admin._dict_2_entry(
                {
                    'a': '1',
                    'd': {
                        'x': 1
                    }
                },
                schema
            ),
            {
                'a': ['1'],
                'd': ['{"x": 1}']
            }
        )

    def test__entry_plain_keys(self):
        """Test entry extraction.
        """
        # pylint: disable=protected-access
        self.assertEqual(
            admin._entry_plain_keys(
                {
                    'test-key;tm-test-0': ['a'],
                    'test-b;tm-test-0': ['a', 'b'],
                    'test-c;tm-test-0': ['42'],
                    'test-d;tm-test-0': [True],
                    'test-key;tm-test-1': ['b'],
                    'test-b;tm-test-1': ['c'],
                    'test-c;tm-test-1': ['43'],
                    'test-d;tm-test-1': [False],
                    'test-key;tm-test-2': ['c'],
                    'test-b;tm-test-2': [],
                    'test-c;tm-test-2': ['44'],
                    'test-d;tm-test-2': [True],
                }
            ),
            [
                'test-b',
                'test-c',
                'test-d',
                'test-key',
            ]
        )

    def test__to_obj_list(self):
        """Test object list LDAP serialization.
        """
        # pylint: disable=protected-access
        schema = [
            ('test-key', 'key', str),
            ('test-b', 'b', [str]),
            ('test-c', 'c', int),
            ('test-d', 'd', bool),
        ]

        self.assertEqual(
            admin._to_obj_list(
                [],
                'key',
                'tm-test',
                schema
            ),
            {
                'test-key': [],
                'test-b': [],
                'test-c': [],
                'test-d': [],
            }
        )

        self.assertEqual(
            admin._to_obj_list(
                [
                    {
                        'key': 'a',
                        'b': ['a', 'b'],
                        'c': 42,
                        'd': True,
                    },
                    {
                        'key': 'b',
                        'b': ['c'],
                        'c': 43,
                        'd': False,
                    },
                    {
                        'key': 'c',
                        'b': [],
                        'c': 44,
                        'd': True,
                    },
                ],
                'key',
                'tm-test',
                schema
            ),
            {
                'test-key;tm-test-0': ['a'],
                'test-b;tm-test-0': ['a', 'b'],
                'test-c;tm-test-0': ['42'],
                'test-d;tm-test-0': [True],
                'test-key;tm-test-1': ['b'],
                'test-b;tm-test-1': ['c'],
                'test-c;tm-test-1': ['43'],
                'test-d;tm-test-1': [False],
                'test-key;tm-test-2': ['c'],
                # FIXME: LDAP Admin serialization "optimizes" out empty lists.
                # 'test-b;tm-test-2': [],
                'test-c;tm-test-2': ['44'],
                'test-d;tm-test-2': [True],

            }
        )

    def test_group_by_opt(self):
        """Tests group by attribute option."""
        # Disable W0212: Test access protected members of admin module.
        # pylint: disable=protected-access
        self.assertEqual(
            admin._group_entry_by_opt(
                {
                    'xxx;a': ['1'],
                    'xxx;b': ['3'],
                    'yyy;a': ['2'],
                }
            ),
            {
                'a': [
                    ('xxx', 'a', ['1']),
                    ('yyy', 'a', ['2']),
                ],
                'b': [
                    ('xxx', 'b', ['3']),
                ],
            },
        )

    def test_grouped_to_list_of_dict(self):
        """Test conversion of grouped by opt elements to dicts."""
        # Disable W0212: Test access protected members of admin module.
        # pylint: disable=W0212
        self.assertEqual(
            admin._grouped_to_list_of_dict(
                {
                    'tm-ep-1': [
                        ('name', 'tm-ep-1', ['http']),
                        ('port', 'tm-ep-1', ['80']),
                        ('service-name', 'tm-s-1', ['x'])
                    ],
                    'tm-ep-2': [
                        ('name', 'tm-ep-2', ['tcp']),
                        ('port', 'tm-ep-2', ['1000']),
                        ('service-name', 'tm-s-2', ['x'])
                    ],
                },
                'tm-ep-',
                [
                    ('name', 'name', str),
                    ('port', 'port', int)
                ]
            ),
            [
                {'name': 'http', 'port': 80},
                {'name': 'tcp', 'port': 1000}
            ],
        )

    def test_remove_empty(self):
        """Test removal of empty values from entry."""
        # Access to protected member.
        #
        # pylint: disable=W0212
        self.assertEqual(
            {'aaa': ['a']},
            admin._remove_empty({'aaa': ['a'], 'b': [], 'c': {'a': []}})
        )

    def test_app_to_entry(self):
        """Tests convertion of app dictionary to ldap entry."""
        app = {
            '_id': 'xxx',
            'cpu': '100%',
            'memory': '1G',
            'disk': '1G',
            'tickets': ['a', None, 'b'],
            'features': [],
            'args': [],
            'environ': [
                {'name': 'BAR', 'value': '34567'},
                {'name': 'FOO', 'value': '12345'},
            ],
            'services': [
                {
                    'name': 'a',
                    'command': '/a',
                    'restart': {
                        'limit': 3,
                        'interval': 30,
                    },
                },
                {
                    'name': 'b',
                    'command': '/b',
                },
                {
                    'name': 'c',
                    'command': '/c',
                    'restart': {
                        'limit': 0,
                    },
                },
            ],
            'endpoints': [
                {'name': 'x', 'port': 1, 'type': 'infra', 'proto': 'udp'},
                {'name': 'y', 'port': 2, 'type': 'infra'},
            ],
            'affinity_limits': {'server': 1, 'rack': 2},
            'passthrough': [],
            'ephemeral_ports': {
                'tcp': 5,
                'udp': 10,
            },
            'shared_ip': True,
            'shared_network': True,
            'traits': ['foo'],
        }

        ldap_entry = {
            'app': ['xxx'],
            'cpu': ['100%'],
            'memory': ['1G'],
            'disk': ['1G'],
            'ticket': ['a', 'b'],
            'trait': ['foo'],
            'service-name;tm-service-0': ['a'],
            'service-name;tm-service-1': ['b'],
            'service-name;tm-service-2': ['c'],
            'service-restart-limit;tm-service-0': ['3'],
            'service-restart-limit;tm-service-1': ['5'],
            'service-restart-limit;tm-service-2': ['0'],
            'service-restart-interval;tm-service-0': ['30'],
            'service-restart-interval;tm-service-1': ['60'],
            'service-restart-interval;tm-service-2': ['60'],
            'service-command;tm-service-0': ['/a'],
            'service-command;tm-service-1': ['/b'],
            'service-command;tm-service-2': ['/c'],
            'endpoint-name;tm-endpoint-0': ['x'],
            'endpoint-name;tm-endpoint-1': ['y'],
            'endpoint-port;tm-endpoint-0': ['1'],
            'endpoint-port;tm-endpoint-1': ['2'],
            'endpoint-type;tm-endpoint-0': ['infra'],
            'endpoint-type;tm-endpoint-1': ['infra'],
            'endpoint-proto;tm-endpoint-0': ['udp'],
            'envvar-name;tm-envvar-0': ['BAR'],
            'envvar-value;tm-envvar-0': ['34567'],
            'envvar-name;tm-envvar-1': ['FOO'],
            'envvar-value;tm-envvar-1': ['12345'],
            'affinity-level;tm-affinity-0': ['rack'],
            'affinity-limit;tm-affinity-0': ['2'],
            'affinity-level;tm-affinity-1': ['server'],
            'affinity-limit;tm-affinity-1': ['1'],
            'ephemeral-ports-tcp': ['5'],
            'ephemeral-ports-udp': ['10'],
            'shared-ip': [True],
            'shared-network': [True]
        }

        # TODO this logs "Expected [<class 'str'>], got ['a', None, 'b']"
        # see treadmill.admin:_dict_2_entry
        self.assertEqual(ldap_entry, admin.Application(None).to_entry(app))

        # When converting to entry, None are skipped, and unicode is converted
        # to str.
        #
        # Adjust app['tickets'] accordingly.
        app['tickets'] = ['a', 'b']
        # Account for default restart values
        app['services'][1]['restart'] = {'limit': 5, 'interval': 60}
        app['services'][2]['restart']['interval'] = 60

        self.assertEqual(app, admin.Application(None).from_entry(ldap_entry))

    def test_app_to_entry_docker(self):
        """Tests convertion of app dictionary to ldap entry."""
        app = {
            '_id': 'xxx',
            'cpu': '100%',
            'memory': '1G',
            'disk': '1G',
            'tickets': [],
            'features': [],
            'endpoints': [],
            'environ': [],
            'traits': ['foo'],
            'services': [
                {
                    'name': 'foo',
                    'image': 'testimage',
                    'useshell': True,
                    'command': 'echo',
                    'restart': {
                        'limit': 3,
                        'interval': 30,
                    },
                },
            ]
        }

        ldap_entry = {
            'app': ['xxx'],
            'cpu': ['100%'],
            'disk': ['1G'],
            'memory': ['1G'],
            'trait': ['foo'],
            # Affinities
            'affinity-level': [],
            'affinity-limit': [],
            # Endpoints
            'endpoint-name': [],
            'endpoint-port': [],
            'endpoint-proto': [],
            'endpoint-type': [],
            # Envvars
            'envvar-name': [],
            'envvar-value': [],
            # Services
            'service-command;tm-service-0': ['echo'],
            'service-image;tm-service-0': ['testimage'],
            'service-name;tm-service-0': ['foo'],
            'service-restart-interval;tm-service-0': ['30'],
            'service-restart-limit;tm-service-0': ['3'],
            'service-useshell;tm-service-0': [True],
        }
        self.assertEqual(ldap_entry, admin.Application(None).to_entry(app))

        app['affinity_limits'] = {}
        app['args'] = []
        app['passthrough'] = []
        app['ephemeral_ports'] = {}

        self.assertEqual(app, admin.Application(None).from_entry(ldap_entry))

    def test_app_to_entry_and_back(self):
        """Test converting app to/from entry populating default values."""
        app = {
            'cpu': '100%',
            'memory': '1G',
            'disk': '1G',
            'services': [{'command': '/a',
                          'name': 'a',
                          'restart': {'interval': 30, 'limit': 3}}],
            'endpoints': [{'name': 'y', 'port': 2}],
            'traits': [],
        }

        expected = {
            'tickets': [],
            'traits': [],
            'features': [],
            'endpoints': [{'name': 'y', 'port': 2}],
            'environ': [],
            'memory': '1G',
            'services': [{'command': '/a',
                          'name': 'a',
                          'restart': {'interval': 30, 'limit': 3}}],
            'disk': '1G',
            'affinity_limits': {},
            'cpu': '100%',
            'passthrough': [],
            'ephemeral_ports': {},
            'args': []
        }

        admin_app = admin.Application(None)
        self.assertEqual(
            expected,
            admin_app.from_entry(admin_app.to_entry(app))
        )

        app['services'][0]['root'] = True
        expected['services'][0]['root'] = True
        self.assertEqual(
            expected,
            admin_app.from_entry(admin_app.to_entry(app))
        )

        app['vring'] = {
            'cells': ['a', 'b'],
            'rules': [{
                'pattern': 'x.y*',
                'endpoints': ['http', 'tcp'],
            }]
        }

        expected['vring'] = {
            'cells': ['a', 'b'],
            'rules': [{
                'pattern': 'x.y*',
                'endpoints': ['http', 'tcp'],
            }]
        }

        self.assertEqual(
            expected,
            admin_app.from_entry(admin_app.to_entry(app))
        )

        app['passthrough'] = ['xxx.x.com', 'yyy.x.com']
        expected['passthrough'] = ['xxx.x.com', 'yyy.x.com']

        self.assertEqual(
            expected,
            admin_app.from_entry(admin_app.to_entry(app))
        )

        app['ephemeral_ports'] = {
            'tcp': 10,
        }
        expected['ephemeral_ports'] = {
            'tcp': 10,
            'udp': 0,
        }

        app['schedule_once'] = True
        expected['schedule_once'] = True

        self.assertEqual(
            expected,
            admin_app.from_entry(admin_app.to_entry(app))
        )

        app['data_retention_timeout'] = '30m'
        expected['data_retention_timeout'] = '30m'

        self.assertEqual(
            expected,
            admin_app.from_entry(admin_app.to_entry(app))
        )

        app['lease'] = '3d'
        expected['lease'] = '3d'

        self.assertEqual(
            expected,
            admin_app.from_entry(admin_app.to_entry(app))
        )

    def test_server_to_entry(self):
        """Tests convertion of app dictionary to ldap entry."""
        srv = {
            '_id': 'xxx',
            'cell': 'yyy',
            'partition': 'p',
            'traits': ['a', 'b', 'c'],
            'data': {'a': '1', 'b': '2'},
        }

        ldap_entry = {
            'server': ['xxx'],
            'cell': ['yyy'],
            'partition': ['p'],
            'trait': ['a', 'b', 'c'],
            'data': ['{"a": "1", "b": "2"}'],
        }

        self.assertEqual(
            admin.Server(None).to_entry(srv),
            ldap_entry
        )
        self.assertEqual(
            admin.Server(None).from_entry(ldap_entry),
            srv
        )

    def test_cell_to_entry(self):
        """Tests conversion of cell to ldap entry."""
        cell = {
            '_id': 'test',
            'username': 'xxx',
            'location': 'x',
            'archive-server': 'y',
            'archive-username': 'z',
            'version': '1.2.3',
            'root': '',
            'ssq-namespace': 's',
            'masters': [
                {'idx': 1,
                 'hostname': 'abc',
                 'zk-client-port': 5000,
                 'zk-jmx-port': 6000,
                 'zk-followers-port': 7000,
                 'zk-election-port': 8000}
            ],
            'data': {'foo': 'bar', 'x': 'y'},
            'traits': [],
        }
        cell_admin = admin.Cell(None)
        self.assertEqual(
            cell,
            cell_admin.from_entry(cell_admin.to_entry(cell))
        )

    @mock.patch('treadmill.admin._ldap._TREADMILL_ATTR_OID_PREFIX', '1.2.3.')
    def test_attrtype_to_str(self):
        """Tests conversion of attribute type to LDIF string."""
        # pylint: disable=protected-access
        result = admin._attrtype_2_str({
            'idx': 4,
            'name': 'name',
            'desc': 'desc',
            'syntax': 'syntax',
            'equality': 'foo',
            'substr': 'substr',
            'ordering': 'ordering',
            'single_value': True
        })
        self.assertEqual(result, (
            '( 1.2.3.4 '
            'NAME \'name\' '
            'DESC \'desc\' '
            'SYNTAX syntax '
            'EQUALITY foo '
            'SUBSTR substr '
            'ORDERING ordering '
            'SINGLE-VALUE '
            ')'
        ))

    @mock.patch('treadmill.admin._ldap._TREADMILL_OBJCLS_OID_PREFIX', '1.2.3.')
    def test_objcls_to_str(self):
        """Tests conversion of object class to LDIF string."""
        # pylint: disable=protected-access
        result = admin._objcls_2_str('name', {
            'idx': 4,
            'desc': 'desc',
            'must': ['one', 'two', 'three'],
            'may': ['four', 'five']
        })
        self.assertEqual(result, (
            '( 1.2.3.4 '
            'NAME \'name\' '
            'DESC \'desc\' '
            'SUP top STRUCTURAL '
            'MUST ( one $ two $ three ) '
            'MAY ( four $ five ) '
            ')'
        ))
        result = admin._objcls_2_str('name', {
            'idx': 4,
            'desc': 'desc',
            'must': ['foo']
        })
        self.assertEqual(result, (
            '( 1.2.3.4 '
            'NAME \'name\' '
            'DESC \'desc\' '
            'SUP top STRUCTURAL '
            'MUST ( foo ) '
            ')'
        ))

    def test_schema(self):
        """Test schema parsing."""
        # Disable W0212: Test access protected members of admin module.
        # pylint: disable=W0212
        attrs = [
            '{0}( %s NAME x1 DESC \'x x\''
            ' ORDERING integerOrderingMatch'
            ' SYNTAX 1.3.6.1.4.1.1466.115.121.1.27'
            ' )' % (admin._TREADMILL_ATTR_OID_PREFIX + '11'),
            '{1}( %s NAME x2 DESC \'x x\''
            ' SUBSTR caseIgnoreSubstringsMatch'
            ' EQUALITY caseIgnoreMatch'
            ' SYNTAX 1.3.6.1.4.1.1466.115.121.1.15'
            ' )' % (admin._TREADMILL_ATTR_OID_PREFIX + '22'),
        ]

        obj_classes = [
            '{0}( %s NAME o1 DESC \'x x\''
            ' SUP top STRUCTURAL'
            ' MUST ( xxx ) MAY ( a $ b )'
            ' )' % (admin._TREADMILL_OBJCLS_OID_PREFIX + '33'),
        ]

        admin_obj = admin.Admin(None, None)
        admin_obj.ldap = ldap3.Connection(ldap3.Server('fake'),
                                          client_strategy=ldap3.MOCK_SYNC)

        admin_obj.ldap.strategy.add_entry(
            'cn={1}treadmill,cn=schema,cn=config',
            {'olcAttributeTypes': attrs, 'olcObjectClasses': obj_classes}
        )

        admin_obj.ldap.bind()

        self.assertEqual(
            {
                'dn': 'cn={1}treadmill,cn=schema,cn=config',
                'objectClasses': {
                    'o1': {
                        'idx': 33,
                        'desc': 'x x',
                        'must': ['xxx'],
                        'may': ['a', 'b'],
                    },
                },
                'attributeTypes': {
                    'x1': {
                        'idx': 11,
                        'desc': 'x x',
                        'type': 'int'
                    },
                    'x2': {
                        'idx': 22,
                        'desc': 'x x',
                        'type': 'str',
                        'ignore_case': True
                    },
                }
            },
            admin_obj.schema()
        )

    @mock.patch('ldap3.Connection.add', mock.Mock())
    def test_init(self):
        """Tests init logic."""
        admin_obj = admin.Admin(None, 'dc=test,dc=com')
        admin_obj.write_ldap = ldap3.Connection(
            ldap3.Server('fake'), client_strategy=ldap3.MOCK_SYNC
        )

        admin_obj.init()

        dn_list = [
            arg[0][0] for arg in admin_obj.write_ldap.add.call_args_list
        ]

        self.assertTrue('dc=test,dc=com' in dn_list)
        self.assertTrue('ou=treadmill,dc=test,dc=com' in dn_list)
        self.assertTrue('ou=apps,ou=treadmill,dc=test,dc=com' in dn_list)

    @mock.patch('ldap3.Connection.add', mock.Mock())
    def test_add(self):
        """Tests add logic."""
        admin_obj = admin.Admin(None, 'dc=test,dc=com')
        admin_obj.write_ldap = ldap3.Connection(
            ldap3.Server('fake'), client_strategy=ldap3.MOCK_SYNC
        )

        admin_obj.add(
            'ou=example,dc=test,dc=com',
            'testClass',
            {
                'foo': 1,
                'bar': ['z', 'a'],
                'lot': 2,
                'exp': [3, 4]
            }
        )

        call = admin_obj.write_ldap.add.call_args_list[0][0]
        self.assertEqual(call[0], 'ou=example,dc=test,dc=com')
        self.assertEqual(call[1], 'testClass')
        self.assertEqual(
            [attr for attr in six.iteritems(call[2])],
            [('bar', ['z', 'a']), ('exp', [3, 4]), ('foo', 1), ('lot', 2)]
        )

    @mock.patch('treadmill.admin._ldap.Admin.modify', mock.Mock())
    @mock.patch('treadmill.admin._ldap.Admin.paged_search', mock.Mock())
    def test_update(self):
        """Tests update logic.
        """
        mock_admin = admin.Admin(None, 'dc=test,dc=com')
        mock_admin.paged_search.return_value = [
            (
                'cell=xxx,allocation=prod1,...',
                {
                    'disk': ['2G'],
                    'trait': ['a', 'b'],
                    'priority;tm-alloc-assignment-123': [80],
                    'pattern;tm-alloc-assignment-123': ['ppp.ttt'],
                    'priority;tm-alloc-assignment-345': [60],
                    'pattern;tm-alloc-assignment-345': ['ppp.ddd'],
                }
            )
        ]

        mock_admin.update(
            'cell=xxx,allocation=prod1,...',
            {
                'disk': ['1G'],
                'trait': ['a'],
                'priority;tm-alloc-assignment-0': [80],
                'pattern;tm-alloc-assignment-0': ['ppp.ttt'],
                'priority;tm-alloc-assignment-345': [30],
                'pattern;tm-alloc-assignment-345': ['ppp.ddd'],
            }
        )

        mock_admin.paged_search.assert_called_once_with(
            search_base=mock.ANY,
            search_scope=mock.ANY,
            search_filter=mock.ANY,
            attributes=[
                'disk',
                'pattern',
                'priority',
                'trait',
            ],
            dirty=False,
        )
        mock_admin.modify.assert_called_once_with(
            'cell=xxx,allocation=prod1,...',
            {
                'disk': [('MODIFY_REPLACE', ['1G'])],
                'trait': [('MODIFY_REPLACE', ['a'])],
                'priority;tm-alloc-assignment-123': [('MODIFY_DELETE', [])],
                'pattern;tm-alloc-assignment-123': [('MODIFY_DELETE', [])],
                'pattern;tm-alloc-assignment-0': [('MODIFY_ADD', ['ppp.ttt'])],
                'priority;tm-alloc-assignment-0': [('MODIFY_ADD', [80])],
                'priority;tm-alloc-assignment-345': [('MODIFY_REPLACE', [30])]
            }
        )


class TenantTest(unittest.TestCase):
    """Tests Tenant ldapobject routines."""

    def setUp(self):
        self.tnt = admin.Tenant(admin.Admin(None, 'dc=xx,dc=com'))

    def test_to_entry(self):
        """Tests convertion of tenant dictionary to ldap entry."""
        tenant = {'tenant': 'foo', 'systems': [3032]}
        ldap_entry = {
            'tenant': ['foo'],
            'system': ['3032'],
        }

        self.assertEqual(ldap_entry, self.tnt.to_entry(tenant))
        self.assertEqual(tenant, self.tnt.from_entry(ldap_entry))

        tenant = {'tenant': 'foo:bar', 'systems': [3032]}
        ldap_entry = {
            'tenant': ['foo:bar'],
            'system': ['3032'],
        }
        self.assertEqual(tenant, self.tnt.from_entry(ldap_entry))
        self.assertTrue(
            self.tnt.dn('foo:bar').startswith(
                'tenant=bar,tenant=foo,ou=allocations,'))


class AllocationTest(unittest.TestCase):
    """Tests Allocation ldapobject routines."""

    def setUp(self):
        self.alloc = admin.Allocation(
            admin.Admin(None, 'dc=xx,dc=com'))

    def test_dn(self):
        """Tests allocation identity to dn mapping."""
        self.assertTrue(
            self.alloc.dn('foo:bar/prod1').startswith(
                'allocation=prod1,tenant=bar,tenant=foo,ou=allocations,'
            )
        )

    def test_to_entry(self):
        """Tests conversion of allocation to LDAP entry."""
        obj = {'environment': 'prod'}
        ldap_entry = {
            'environment': ['prod'],
        }
        self.assertEqual(ldap_entry, self.alloc.to_entry(obj))

    @mock.patch('treadmill.admin._ldap.Admin.paged_search', mock.Mock())
    @mock.patch('treadmill.admin._ldap.LdapObject.get',
                mock.Mock(return_value={}))
    def test_get(self):
        """Tests loading cell allocations."""
        # Disable warning about accessing protected member _ldap
        # pylint: disable=W0212
        treadmill.admin._ldap.Admin.paged_search.return_value = [
            ('cell=xxx,allocation=prod1,...',
             {'cell': ['xxx'],
              'memory': ['1G'],
              'cpu': ['100%'],
              'disk': ['2G'],
              'rank': [100],
              'trait': ['a', 'b'],
              'priority;tm-alloc-assignment-123': [80],
              'pattern;tm-alloc-assignment-123': ['ppp.ttt'],
              'priority;tm-alloc-assignment-345': [60],
              'pattern;tm-alloc-assignment-345': ['ppp.ddd']})
        ]
        obj = self.alloc.get('foo:bar/prod1')
        treadmill.admin._ldap.Admin.paged_search.assert_called_with(
            attributes=mock.ANY,
            search_base='allocation=prod1,tenant=bar,tenant=foo,'
                        'ou=allocations,ou=treadmill,dc=xx,dc=com',
            search_filter='(&(objectclass=tmCellAllocation))',
            dirty=False
        )
        self.assertEqual(obj['reservations'][0]['cell'], 'xxx')
        self.assertEqual(obj['reservations'][0]['disk'], '2G')
        self.assertEqual(obj['reservations'][0]['rank'], 100)
        self.assertEqual(obj['reservations'][0]['traits'], ['a', 'b'])
        self.assertIn(
            {'pattern': 'ppp.ttt', 'priority': 80},
            obj['reservations'][0]['assignments'])


class CellAllocationTest(unittest.TestCase):
    """Tests CellAllocation ldapobject routines."""

    def setUp(self):
        self.cell_alloc = admin.CellAllocation(
            admin.Admin(None, 'dc=xx,dc=com'))

    def test_dn(self):
        """Tests cell allocation identity to dn mapping."""
        self.assertTrue(
            self.cell_alloc.dn(['somecell', 'foo:bar/prod1']).startswith(
                'cell=somecell,allocation=prod1,'
                'tenant=bar,tenant=foo,ou=allocations,'))

    def test_to_entry(self):
        """Tests conversion of cell allocation to LDAP entry."""
        obj = {
            'cell': 'somecell',
            'cpu': '100%',
            'memory': '10G',
            'disk': '100G',
            'rank': 100,
            'rank_adjustment': 10,
            'partition': '_default',
            'max_utilization': 4.2,
            'traits': ['a', 'b'],
        }
        self.assertEqual(
            self.cell_alloc.to_entry(obj),
            {
                'cell': ['somecell'],
                'cpu': ['100%'],
                'memory': ['10G'],
                'disk': ['100G'],
                'rank': ['100'],
                'rank-adjustment': ['10'],
                'partition': ['_default'],
                'max-utilization': ['4.2'],
                'trait': ['a', 'b'],
                # Assignments
                'pattern': [],
                'priority': [],
            }
        )

        obj.update({
            'assignments': [
                {'pattern': 'foo.*', 'priority': 1},
                {'pattern': 'bar.*', 'priority': 2},
            ],
        })
        self.assertEqual(
            self.cell_alloc.to_entry(obj),
            {
                'cell': ['somecell'],
                'cpu': ['100%'],
                'memory': ['10G'],
                'disk': ['100G'],
                'rank': ['100'],
                'rank-adjustment': ['10'],
                'partition': ['_default'],
                'max-utilization': ['4.2'],
                'trait': ['a', 'b'],
                # Assignments
                'pattern;tm-alloc-assignment-0': ['bar.*'],
                'priority;tm-alloc-assignment-0': ['2'],
                'pattern;tm-alloc-assignment-1': ['foo.*'],
                'priority;tm-alloc-assignment-1': ['1'],
            }
        )


class PartitionTest(unittest.TestCase):
    """Tests Partition ldapobject routines."""

    def setUp(self):
        self.part = admin.Partition(
            admin.Admin(None, 'dc=xx,dc=com'))

    def test_dn(self):
        """Test partition identity to dn mapping."""
        self.assertTrue(
            self.part.dn(['foo', 'bar']).startswith(
                'partition=foo,cell=bar,ou=cells,'
            )
        )

    def test_to_entry(self):
        """Tests conversion of partition to LDAP entry."""
        obj = {
            '_id': 'foo',
            'memory': '4G',
            'cpu': '42%',
            'disk': '100G',
            'down-threshold': 42,
            'systems': [],
            'limits': [
                {
                    'trait': 'foo',
                    'cpu': '10%',
                    'disk': '1G',
                    'memory': '1G',
                }
            ]
        }

        ldap_entry = {
            'partition': ['foo'],
            'memory': ['4G'],
            'cpu': ['42%'],
            'disk': ['100G'],
            'down-threshold': ['42'],
            # allocation limits
            'allocation-limit-trait;tm-alloc-limit-0': ['foo'],
            'allocation-limit-cpu;tm-alloc-limit-0': ['10%'],
            'allocation-limit-disk;tm-alloc-limit-0': ['1G'],
            'allocation-limit-memory;tm-alloc-limit-0': ['1G'],
        }

        self.assertEqual(ldap_entry, self.part.to_entry(obj))
        self.assertEqual(obj, self.part.from_entry(ldap_entry))


class ServerTest(unittest.TestCase):
    """Tests Server ldapobject routines."""

    def setUp(self):
        self.server = admin.Server(
            admin.Admin(None, 'dc=xx,dc=com'))

    @mock.patch('treadmill.admin._ldap.Admin.get')
    def test_get(self, get_mock):
        """Test getting server from LDAP."""
        get_mock.return_value = {
            'server': ['xxx'],
            'cell': ['yyy'],
            'partition': ['p'],
        }

        server = self.server.get('xxx')

        self.assertEqual(
            server,
            {'_id': 'xxx', 'cell': 'yyy', 'partition': 'p', 'traits': []}
        )
        get_mock.assert_called_once_with(
            'server=xxx,ou=servers,ou=treadmill,dc=xx,dc=com',
            mock.ANY,
            ['server', 'cell', 'trait', 'partition', 'data'],
            dirty=False
        )

    @mock.patch('treadmill.admin._ldap.Admin.get')
    def test_get_operational_attrs(self, get_mock):
        """Test getting server from LDAP with operational attrs."""
        get_mock.return_value = {
            'server': ['xxx'],
            'cell': ['yyy'],
            'partition': ['p'],
            'createTimestamp': datetime.datetime(
                2018, 11, 20, 21, 22, 23, tzinfo=datetime.timezone.utc
            ),
            'modifyTimestamp': datetime.datetime(
                2018, 11, 21, 21, 22, 23, tzinfo=datetime.timezone.utc
            ),
        }

        server = self.server.get('xxx', get_operational_attrs=True)

        self.assertEqual(
            server,
            {
                '_id': 'xxx',
                'cell': 'yyy',
                'partition': 'p',
                'traits': [],
                '_create_timestamp': 1542748943.0,
                '_modify_timestamp': 1542835343.0,
            }
        )
        get_mock.assert_called_once_with(
            'server=xxx,ou=servers,ou=treadmill,dc=xx,dc=com',
            mock.ANY,
            [
                'server', 'cell', 'trait', 'partition', 'data',
                'createTimestamp', 'modifyTimestamp'
            ],
            dirty=False
        )

    @mock.patch('treadmill.admin._ldap.Admin.paged_search')
    def test_list(self, paged_search_mock):
        """Test getting a list of servers from LDAP."""
        paged_search_mock.return_value = [
            (
                'server=xxx,ou=servers,ou=treadmill,dc=xx,dc=com',
                {
                    'server': ['xxx'],
                    'cell': ['yyy'],
                    'partition': ['p'],
                },
            ),
            (
                'server=zzz,ou=servers,ou=treadmill,dc=xx,dc=com',
                {
                    'server': ['zzz'],
                    'cell': ['yyy'],
                    'partition': ['p'],
                },
            )
        ]

        servers = self.server.list({'cell': 'yyy'})

        self.assertEqual(
            servers,
            [
                {'_id': 'xxx', 'cell': 'yyy', 'partition': 'p', 'traits': []},
                {'_id': 'zzz', 'cell': 'yyy', 'partition': 'p', 'traits': []},
            ]
        )
        paged_search_mock.assert_called_once_with(
            search_base='ou=servers,ou=treadmill,dc=xx,dc=com',
            search_filter='(&(objectClass=tmServer)(cell=yyy))',
            search_scope='SUBTREE',
            attributes=['server', 'cell', 'trait', 'partition', 'data'],
            dirty=False
        )

    @mock.patch('treadmill.admin._ldap.Admin.paged_search')
    def test_list_operational_attrs(self, paged_search_mock):
        """Test getting a list of servers from LDAP with operational attrs."""
        paged_search_mock.return_value = [
            (
                'server=xxx,ou=servers,ou=treadmill,dc=xx,dc=com',
                {
                    'server': ['xxx'],
                    'cell': ['yyy'],
                    'partition': ['p'],
                    'createTimestamp': datetime.datetime(
                        2018, 11, 20, 21, 22, 23, tzinfo=datetime.timezone.utc
                    ),
                    'modifyTimestamp': datetime.datetime(
                        2018, 11, 21, 21, 22, 23, tzinfo=datetime.timezone.utc
                    ),
                },
            ),
            (
                'server=zzz,ou=servers,ou=treadmill,dc=xx,dc=com',
                {
                    'server': ['zzz'],
                    'cell': ['yyy'],
                    'partition': ['p'],
                    'createTimestamp': datetime.datetime(
                        2018, 11, 22, 21, 22, 23, tzinfo=datetime.timezone.utc
                    ),
                    'modifyTimestamp': datetime.datetime(
                        2018, 11, 23, 21, 22, 23, tzinfo=datetime.timezone.utc
                    ),
                },
            )
        ]

        servers = self.server.list({'cell': 'yyy'}, get_operational_attrs=True)

        self.assertEqual(
            servers,
            [
                {
                    '_id': 'xxx',
                    'cell': 'yyy',
                    'partition': 'p',
                    'traits': [],
                    '_create_timestamp': 1542748943.0,
                    '_modify_timestamp': 1542835343.0,
                },
                {
                    '_id': 'zzz',
                    'cell': 'yyy',
                    'partition': 'p',
                    'traits': [],
                    '_create_timestamp': 1542921743.0,
                    '_modify_timestamp': 1543008143.0,
                },
            ]
        )
        paged_search_mock.assert_called_once_with(
            search_base='ou=servers,ou=treadmill,dc=xx,dc=com',
            search_filter='(&(objectClass=tmServer)(cell=yyy))',
            search_scope='SUBTREE',
            attributes=[
                'server', 'cell', 'trait', 'partition', 'data',
                'createTimestamp', 'modifyTimestamp'
            ],
            dirty=False
        )


if __name__ == '__main__':
    unittest.main()
