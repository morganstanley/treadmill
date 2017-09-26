"""Unit test for treadmill admin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


# Disable C0302: Too many lines in the module
# pylint: disable=C0302

import hashlib
import unittest
import io

import mock
import ldap3

import treadmill
from treadmill import admin


def _open_side_effect_for_simple_auth(path, *args):
    if path == '/root/.treadmill_ldap':
        return io.StringIO("secret")
    elif path.endswith('deploy/config/treadmill.yml'):
        return io.StringIO(
            """
            domain: tm.treadmill
            freeipa_server:
                authentication: simple
                remote_admin_pwd_file: /root/.treadmill_ldap
            """)
    else:
        return open(path, *args)


def _open_side_effect_for_sasl_auth(path, *args):
    if path == '/root/.treadmill_ldap':
        return io.StringIO("secret")
    elif path.endswith('deploy/config/treadmill.yml'):
        return io.StringIO(
            """
            domain: tm.treadmill
            freeipa_server:
                authentication: sasl
                remote_admin_pwd_file: /root/.treadmill/.ldap
            """)
    else:
        return open(path, *args)


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
        ]

        self.assertEqual(
            {'a': '1', 'b': ['x'], 'C': 1},
            admin._entry_2_dict(
                {'a': ['1'], 'b': ['x'], 'c': ['1']}, schema
            )
        )
        self.assertEqual(
            {'a': '1', 'b': ['x'], 'd': {'x': 1}},
            admin._entry_2_dict(
                {
                    'a': ['1'],
                    'b': ['x'],
                    'd': ['{"x": 1}']
                },
                schema
            )
        )
        self.assertEqual(
            {'a': ['1'], 'b': ['x'], 'c': ['1']},
            admin._dict_2_entry(
                {
                    'a': '1',
                    'b': ['x'],
                    'C': 1
                },
                schema
            )
        )
        self.assertEqual(
            {'a': ['1'], 'd': ['{"x": 1}']},
            admin._dict_2_entry(
                {
                    'a': '1',
                    'd': {'x': 1}
                },
                schema
            )
        )

    def test_group_by_opt(self):
        """Tests group by attribute option."""
        # Disable W0212: Test access protected members of admin module.
        # pylint: disable=W0212
        self.assertEqual(
            sorted(
                {
                    'a': [('xxx', 'a', ['1']), ('yyy', 'a', ['2'])],
                    'b': [('xxx', 'b', ['3'])]}
            ),
            sorted(
                admin._group_entry_by_opt(
                    {'xxx;a': ['1'], 'xxx;b': ['3'], 'yyy;a': ['2']}
                )
            )
        )

    def test_grouped_to_list_of_dict(self):
        """Test conversion of grouped by opt elements to dicts."""
        # Disable W0212: Test access protected members of admin module.
        # pylint: disable=W0212
        self.assertEqual(
            [{'name': 'http', 'port': 80}, {'name': 'tcp', 'port': 1000}],
            admin._grouped_to_list_of_dict(
                {'tm-ep-1': [('name', 'tm-ep-1', ['http']),
                             ('port', 'tm-ep-1', ['80']),
                             ('service-name', 'tm-s-1', ['x'])],
                 'tm-ep-2': [('name', 'tm-ep-2', ['tcp']),
                             ('port', 'tm-ep-2', ['1000']),
                             ('service-name', 'tm-s-2', ['x'])]},
                'tm-ep-',
                [('name', 'name', str), ('port', 'port', int)]))

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
            'environ': [{'name': 'a', 'value': 'b'}],
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
            'shared_network': True
        }

        md5_a = hashlib.md5(b'a').hexdigest()
        md5_b = hashlib.md5(b'b').hexdigest()
        md5_c = hashlib.md5(b'c').hexdigest()
        md5_x = hashlib.md5(b'x').hexdigest()
        md5_y = hashlib.md5(b'y').hexdigest()
        md5_srv = hashlib.md5(b'server').hexdigest()
        md5_rack = hashlib.md5(b'rack').hexdigest()

        ldap_entry = {
            'app': ['xxx'],
            'cpu': ['100%'],
            'memory': ['1G'],
            'disk': ['1G'],
            'ticket': ['a', 'b'],
            'service-name;tm-service-' + md5_a: ['a'],
            'service-name;tm-service-' + md5_b: ['b'],
            'service-name;tm-service-' + md5_c: ['c'],
            'service-restart-limit;tm-service-' + md5_a: ['3'],
            'service-restart-limit;tm-service-' + md5_b: ['5'],
            'service-restart-limit;tm-service-' + md5_c: ['0'],
            'service-restart-interval;tm-service-' + md5_a: ['30'],
            'service-restart-interval;tm-service-' + md5_b: ['60'],
            'service-restart-interval;tm-service-' + md5_c: ['60'],
            'service-command;tm-service-' + md5_a: ['/a'],
            'service-command;tm-service-' + md5_b: ['/b'],
            'service-command;tm-service-' + md5_c: ['/c'],
            'endpoint-name;tm-endpoint-' + md5_x: ['x'],
            'endpoint-name;tm-endpoint-' + md5_y: ['y'],
            'endpoint-port;tm-endpoint-' + md5_x: ['1'],
            'endpoint-port;tm-endpoint-' + md5_y: ['2'],
            'endpoint-type;tm-endpoint-' + md5_x: ['infra'],
            'endpoint-type;tm-endpoint-' + md5_y: ['infra'],
            'endpoint-proto;tm-endpoint-' + md5_x: ['udp'],
            'envvar-name;tm-envvar-' + md5_a: ['a'],
            'envvar-value;tm-envvar-' + md5_a: ['b'],
            'affinity-level;tm-affinity-' + md5_srv: ['server'],
            'affinity-limit;tm-affinity-' + md5_srv: ['1'],
            'affinity-level;tm-affinity-' + md5_rack: ['rack'],
            'affinity-limit;tm-affinity-' + md5_rack: ['2'],
            'ephemeral-ports-tcp': ['5'],
            'ephemeral-ports-udp': ['10'],
            'shared-ip': ['TRUE'],
            'shared-network': ['TRUE']
        }

        self.assertEqual(ldap_entry, admin.Application(None).to_entry(app))

        # When converting to entry, None are skipped, and unicode is converted
        # to str.
        #
        # Adjuest app['tickets'] accordingly.
        app['tickets'] = ['a', 'b']
        # Account for default restart values
        app['services'][1]['restart'] = {'limit': 5, 'interval': 60}
        app['services'][2]['restart']['interval'] = 60
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
        }

        expected = {
            'tickets': [],
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

        self.assertEqual(ldap_entry, admin.Server(None).to_entry(srv))
        self.assertEqual(srv, admin.Server(None).from_entry(ldap_entry))

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
        }
        cell_admin = admin.Cell(None)
        self.assertEqual(
            cell,
            cell_admin.from_entry(cell_admin.to_entry(cell))
        )

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
        admin_obj.ldap = ldap3.Connection(ldap3.Server('fake'),
                                          client_strategy=ldap3.MOCK_SYNC)

        admin_obj.init()

        dn_list = [arg[0][0] for arg in admin_obj.ldap.add.call_args_list]

        self.assertTrue('dc=test,dc=com' in dn_list)
        self.assertTrue('ou=treadmill,dc=test,dc=com' in dn_list)
        self.assertTrue('ou=apps,ou=treadmill,dc=test,dc=com' in dn_list)

    @unittest.skip('BROKEN: Fix after LDAP refactor.')
    @mock.patch('ldap3.Connection', mock.Mock())
    @mock.patch('builtins.open', mock.Mock(
        side_effect=_open_side_effect_for_simple_auth))
    @mock.patch('ldap3.Server', mock.Mock(return_value={}))
    def test_ldap3_simple_connection(self):
        """Tests ldap simple credential."""
        admin_obj = admin.Admin("ldap://host:389", None)

        admin_obj.connect()

        ldap3.Connection.assert_called_with({},
                                            user="cn=admin,dc=tm,dc=treadmill",
                                            password="secret",
                                            authentication='SIMPLE',
                                            client_strategy='RESTARTABLE',
                                            sasl_mechanism=None,
                                            auto_bind=True)

    @mock.patch('ldap3.Connection', mock.Mock())
    @mock.patch('builtins.open', mock.Mock(
        side_effect=_open_side_effect_for_sasl_auth))
    @mock.patch('ldap3.Server', mock.Mock(return_value={}))
    def test_ldap3_sasl_connection(self):
        """Tests ldap sasl credential."""
        admin_obj = admin.Admin("ldap://host:389", None)

        admin_obj.connect()

        ldap3.Connection.assert_called_with({},
                                            authentication='SASL',
                                            client_strategy='RESTARTABLE',
                                            sasl_mechanism='GSSAPI',
                                            auto_bind=True)


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
                b'tenant=bar,tenant=foo,ou=allocations,'))


class AllocationTest(unittest.TestCase):
    """Tests Allocation ldapobject routines."""

    def setUp(self):
        self.alloc = admin.Allocation(
            admin.Admin(None, 'dc=xx,dc=com'))

    def test_dn(self):
        """Tests allocation identity to dn mapping."""
        self.assertTrue(
            self.alloc.dn('foo:bar/prod1').startswith(
                b'allocation=prod1,tenant=bar,tenant=foo,ou=allocations,'))

    def test_to_entry(self):
        """Tests conversion of allocation to LDAP entry."""
        obj = {'environment': 'prod'}
        ldap_entry = {
            'environment': ['prod'],
        }
        self.assertEqual(ldap_entry, self.alloc.to_entry(obj))

    @mock.patch('treadmill.admin.Admin.search', mock.Mock())
    @mock.patch('treadmill.admin.LdapObject.get', mock.Mock(return_value={}))
    def test_get(self):
        """Tests loading cell allocations."""
        treadmill.admin.Admin.search.return_value = [
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
        treadmill.admin.Admin.search.assert_called_with(
            attributes=mock.ANY,
            search_base='allocation=prod1,tenant=bar,tenant=foo,'
                        'ou=allocations,ou=treadmill,dc=xx,dc=com',
            search_filter='(objectclass=tmCellAllocation)',
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
            'traits': [],
        }
        ldap_entry = {
            'cell': ['somecell'],
            'cpu': ['100%'],
            'memory': ['10G'],
            'disk': ['100G'],
            'rank': ['100'],
            'rank-adjustment': ['10'],
            'partition': ['_default'],
            'max-utilization': ['4.2'],
        }
        self.assertEqual(ldap_entry, self.cell_alloc.to_entry(obj))

        obj.update({
            'traits': [],
            'assignments': [],
        })
        self.assertEqual(obj, self.cell_alloc.from_entry(ldap_entry))


class PartitionTest(unittest.TestCase):
    """Tests Partition ldapobject routines."""

    def setUp(self):
        self.part = admin.Partition(
            admin.Admin(None, 'dc=xx,dc=com'))

    def test_dn(self):
        """Test partition identity to dn mapping."""
        self.assertTrue(
            self.part.dn(['foo', 'bar']).startswith(
                'partition=foo,cell=bar,ou=cells,'.encode('utf-8')
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
        }

        ldap_entry = {
            'partition': ['foo'],
            'memory': ['4G'],
            'cpu': ['42%'],
            'disk': ['100G'],
            'down-threshold': ['42'],
        }

        self.assertEqual(ldap_entry, self.part.to_entry(obj))
        self.assertEqual(obj, self.part.from_entry(ldap_entry))


if __name__ == '__main__':
    unittest.main()
