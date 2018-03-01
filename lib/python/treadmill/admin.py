"""Low level admin API to manipulate global cell topology.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys

import collections
import copy
import json
import hashlib
import itertools
import logging
import shlex

from distutils import util

import ldap3
from ldap3.core import exceptions as ldap_exceptions
import jinja2
import six

import treadmill.ldap3kerberos

# pylint: disable=too-many-lines
# pylint: disable=C0302

sys.modules['ldap3.protocol.sasl.kerberos'] = treadmill.ldap3kerberos

_LOGGER = logging.getLogger(__name__)

_SYNTAX_2_TYPE = {
    '1.3.6.1.4.1.1466.115.121.1.7': 'bool',
    '1.3.6.1.4.1.1466.115.121.1.15': 'str',
    '1.3.6.1.4.1.1466.115.121.1.12': 'dn',
    '1.3.6.1.4.1.1466.115.121.1.26': 'ias_str',
    '1.3.6.1.4.1.1466.115.121.1.27': 'int',
    '1.3.6.1.4.1.1466.115.121.1.36': 'numeric',
    '1.3.6.1.4.1.1466.115.121.1.38': 'oid',
    '1.3.6.1.4.1.1466.115.121.1.40': 'octets',
}

_TYPE_2_EQUALITY = {
    ('str', False): 'caseExactMatch',
    ('str', True): 'caseIgnoreMatch',
    ('dn', False): 'distinguishedNameMatch',
    ('int', False): 'integerMatch',
}

_TYPE_2_ORDERING = {
    ('int', None): 'integerOrderingMatch',
}

_TYPE_2_SUBSTR = {
    ('str', False): 'caseExactSubstringsMatch',
    ('str', True): 'caseIgnoreSubstringsMatch',
}

_TREADMILL_ATTR_OID_PREFIX = '1.3.6.1.4.1.360.10.6.1.'
_TREADMILL_OBJCLS_OID_PREFIX = '1.3.6.1.4.1.360.10.6.2.'

DEFAULT_PARTITION = '_default'
DEFAULT_TENANT = '_default'


def _entry_2_dict(entry, schema):
    """Convert LDAP entry like object to dict.
    """
    obj = dict()
    for ldap_field, obj_field, field_type in schema:
        if obj_field is None:
            continue

        if ldap_field not in entry:
            if isinstance(field_type, list):
                obj[obj_field] = []
            else:
                obj[obj_field] = None
            continue

        value = entry[ldap_field]
        if isinstance(field_type, list):
            if field_type[0] is str:
                obj[obj_field] = [v for v in value]
            else:
                obj[obj_field] = [field_type[0](v) for v in value]
        elif field_type is bool:
            # XXX: This is necessary until previous bad entries are cleaned up.
            obj[obj_field] = (bool(util.strtobool(value[0].lower()))
                              if not isinstance(value[0], bool) else value[0])
        elif field_type is dict:
            obj[obj_field] = json.loads(value[0])
        elif field_type is str:
            obj[obj_field] = value[0]
        else:
            obj[obj_field] = field_type(value[0])

    return {
        k: v
        for k, v in six.iteritems(obj)
        if v is not None
    }


def _dict_2_entry(obj, schema, option=None, option_value=None):
    """Converts dict to ldap entry."""
    # TODO: refactor to eliminate too many branches warning.
    #
    # pylint: disable=R0912
    entry = dict()

    delete = False
    if '_delete' in obj:
        delete = True

    for ldap_field, obj_field, field_type in schema:
        if obj_field not in obj:
            continue

        value = obj[obj_field]
        if option is not None:
            # We calculate the checksum of the stringification of the value
            checksum = hashlib.md5(six.text_type(option_value).encode())
            ldap_field = ';'.join(
                [
                    ldap_field,
                    '{}-{}'.format(option, checksum.hexdigest())
                ]
            )

        if delete:
            entry[ldap_field] = []
            continue

        if value is None:
            entry[ldap_field] = []
        else:
            if isinstance(field_type, list):
                # TODO: we need to check that all values are of specified type.
                if value:
                    filtered = [
                        six.text_type(v)
                        for v in value
                        if v is not None
                    ]
                    if len(filtered) < len(value):
                        _LOGGER.critical('Exptected %r, got %r',
                                         field_type, value)
                    entry[ldap_field] = filtered
            elif field_type is bool:
                # XXX: This is necessary until previous bad entries are cleaned
                # up.
                entry[ldap_field] = [bool(
                    util.strtobool(six.text_type(value).lower())
                    if not isinstance(value, bool) else value
                )]
            elif field_type is dict:
                entry[ldap_field] = [
                    json.dumps(
                        # Use an OrderedDict to guaranty the stability of the
                        # dictionary key order in the JSON dump.
                        collections.OrderedDict(
                            sorted(value.items(), key=lambda t: t[0])
                        )
                    )
                ]
            else:
                entry[ldap_field] = [six.text_type(value)]

    return entry


def _remove_empty(entry):
    """Remove any empty values and empty lists from entry."""
    new_entry = copy.deepcopy(entry)
    for key, value in six.iteritems(new_entry):
        if isinstance(value, dict):
            new_entry[key] = _remove_empty(value)

    emptykeys = [
        key
        for key, value in six.iteritems(new_entry)
        if not value
    ]
    for key in emptykeys:
        del new_entry[key]

    return new_entry


def _attrtype_2_abstract(attrtype):
    """Converts attribute type to 'abstract' representation."""
    name = attrtype['name']
    syntax = attrtype['syntax']

    abstract = {}

    assert syntax in _SYNTAX_2_TYPE
    abstract['type'] = _SYNTAX_2_TYPE[syntax]
    abstract['desc'] = attrtype['desc']

    if abstract['type'] == 'str':
        if attrtype.get('equality') == 'caseIgnoreMatch':
            abstract['ignore_case'] = True

    abstract['idx'] = attrtype['idx']
    return (name, abstract)


def _abstract_2_attrtype(name, abstract):
    """Converts abstract attribute type to full LDAP definition."""
    attr = {}
    attr['idx'] = abstract['idx']
    attr['oid'] = _TREADMILL_ATTR_OID_PREFIX + six.text_type(attr['idx'])
    attr['name'] = name
    attr['desc'] = abstract.get('desc', name)
    type_2_syntax = {
        v: k
        for k, v in six.iteritems(_SYNTAX_2_TYPE)
    }

    assert abstract['type'] in type_2_syntax
    attr['syntax'] = type_2_syntax[abstract['type']]

    type_case = (abstract['type'], bool(abstract.get('ignore_case')))
    attr['equality'] = _TYPE_2_EQUALITY.get(type_case)
    attr['substr'] = _TYPE_2_SUBSTR.get(type_case)
    attr['ordering'] = _TYPE_2_ORDERING.get(type_case)

    if abstract.get('single_value'):
        attr['single_value'] = True

    if abstract.get('obsolete'):
        attr['obsolete'] = True

    return attr


def _attrtype_2_str(attr):
    """Converts attribute type dictionary to str.
    """
    template = (
        '( {{ oid_pfx }}{{ item.idx }}'
        ' NAME \'{{ item.name }}\''
        ' DESC \'{{ item.desc }}\''
        ' SYNTAX {{ item.syntax }}'
        ' {% if item.equality -%}'
        ' EQUALITY {{ item.equality }}'
        ' {% endif -%}'
        ' {% if item.substr -%}'
        ' SUBSTR {{ item.substr }}'
        ' {% endif -%}'
        ' {% if item.ordering -%}'
        ' ORDERING {{ item.ordering }}'
        ' {% endif -%}'
        ' {% if item.single_value -%}'
        ' SINGLE-VALUE'
        ' {% endif -%} )'
    )

    return six.text_type(
        jinja2.Template(template).render(
            item=attr,
            oid_pfx=_TREADMILL_ATTR_OID_PREFIX
        )
    )


def _objcls_2_abstract(obj_cls):
    """Converts object class to abstract."""
    name = obj_cls['name']
    abstract = {
        'must': obj_cls.get('must', []),
        'may': obj_cls.get('may', []),
        'desc': obj_cls.get('desc', ''),
        'idx': obj_cls['idx'],
    }

    return (name, abstract)


def _objcls_2_str(name, obj_cls):
    """Converts object class dict to string.
    """
    template = (
        '( {{ oid_pfx }}{{ item.idx }}'
        ' NAME \'{{ name }}\''
        ' DESC \'{{ item.desc }}\''
        ' SUP top STRUCTURAL'
        ' MUST ( {{ item.must | join(" $ ") }} )'
        ' {% if item.may -%}'
        ' MAY ( {{ item.may | join(" $ ") }} )'
        ' {% endif -%}'
        ' )'
    )

    return six.text_type(
        jinja2.Template(template).render(
            name=name,
            item=obj_cls,
            oid_pfx=_TREADMILL_OBJCLS_OID_PREFIX
        )
    )


def _group_entry_by_opt(entry):
    """Group by attr;option."""
    attrs_with_opt = [
        tuple(k.split(';') + [entry[k]])
        for k in entry.keys()
        if ';' in k
    ]
    # Sort by option first, field name second
    attrs_with_opt.sort(key=lambda x: (x[1], x[0]))
    return {
        key: list(group)[0::1]
        for key, group in itertools.groupby(
            attrs_with_opt,
            lambda x: x[1]
        )
    }


def _grouped_to_list_of_dict(grouped, prefix, schema):
    """Converts grouped attribute to list of dicts."""
    def _to_dict(values):
        """converts to dict."""
        return _entry_2_dict(
            {
                k: v
                for k, _, v in values
            },
            schema
        )

    filtered = {
        k: v
        for k, v in six.iteritems(grouped)
        if k.startswith(prefix)
    }
    values_list = [
        _to_dict(v) for _k, v in six.iteritems(filtered)
    ]
    return sorted(
        values_list,
        key=lambda x: sorted(list(six.iteritems(x)))
    )


def _dict_normalize(data):
    """Normalize the strings in the dictionary."""
    if isinstance(data, six.string_types):
        return six.text_type(data)
    elif isinstance(data, collections.Mapping):
        return dict([
            _dict_normalize(i)
            for i in six.iteritems(data)
        ])
    elif isinstance(data, collections.Iterable):
        return type(data)([
            _dict_normalize(i) for i in data
        ])
    else:
        return data


def _diff_attribute_values(old_value, new_value):
    """Returns True if the attribute values are different."""
    are_different = len(old_value) != len(new_value)
    if not are_different:
        old_value_dict = dict.fromkeys(old_value)
        new_value_dict = dict.fromkeys(new_value)
        for value in old_value:
            if value not in new_value_dict:
                are_different = True
                break
        if not are_different:
            for value in new_value:
                if value not in old_value_dict:
                    are_different = True
                    break
    return are_different


def _diff_entries(old_entry, new_entry):
    """Diff the entries and produce a diff dictionary suitable for update."""
    # Adapted from python-ldap (http://www.python-ldap.org/) modlist
    # https://github.com/pyldap/pyldap/blob/master/Lib/ldap/modlist.py#L51
    diff = {}
    attrtype_lower_map = {}
    for attr in old_entry.keys():
        attrtype_lower_map[attr.lower()] = attr
    for attrtype in new_entry.keys():
        attrtype_lower = attrtype.lower()
        # Filter away null-strings
        new_values = [
            value
            for value in new_entry[attrtype]
            if value is not None
        ]
        if attrtype_lower in attrtype_lower_map:
            old_values = old_entry.get(attrtype_lower_map[attrtype_lower], [])
            old_values = [
                value
                for value in old_values
                if value is not None
            ]
            del attrtype_lower_map[attrtype_lower]
        else:
            old_values = []

        if not old_values and new_values:
            # Add a new attribute to entry
            diff.setdefault(attrtype, []).append(
                (ldap3.MODIFY_ADD, new_values)
            )
        elif old_values and new_values:
            # Replace existing attribute
            if _diff_attribute_values(old_values, new_values):
                diff.setdefault(attrtype, []).append(
                    (ldap3.MODIFY_REPLACE, new_values))
        elif old_values and not new_values:
            # Completely delete an existing attribute
            diff.setdefault(attrtype, []).append(
                (ldap3.MODIFY_DELETE, []))

    # Remove all attributes of old_entry which are not present
    # in new_entry at all
    for attr in attrtype_lower_map:
        attrtype = attrtype_lower_map[attr]
        diff.setdefault(attrtype, []).append((ldap3.MODIFY_DELETE, []))

    return diff


class AndQuery(object):
    """And query helper."""

    def __init__(self, key, value):
        self.clauses = [(key, value)]

    def __call__(self, key, value):
        """Add constraint."""
        self.clauses.append((key, value))

    def __str__(self):
        return self.to_str()

    def to_str(self):
        """Converts to LDAP query string."""
        paren = ['(%s=%s)' % (k, v) for k, v in self.clauses]
        query = ''.join(paren)
        if len(paren) > 1:
            query = '(&%s)' % query
        return query


class Admin(object):
    """Manages Treadmill objects in ldap.
    """
    # Allow such names as 'dn', 'ou'
    # pylint: disable=invalid-name

    def __init__(self, uri, ldap_suffix, user=None, password=None):
        self.uri = uri
        if uri and not isinstance(uri, list):
            self.uri = uri.split(',')
        self.ldap_suffix = ldap_suffix
        self.root_ou = 'ou=treadmill,%s' % ldap_suffix
        self.ldap = None
        self.user = user
        self.password = password

    def close(self):
        """Closes ldap connection."""
        try:
            if self.ldap:
                self.ldap.unbind()
        except ldap_exceptions.LDAPCommunicationError:
            _LOGGER.exception('cannot close connection.')

    def dn(self, parts):
        """Constructs dn."""
        return ','.join(parts + [self.root_ou])

    def connect(self):
        """Connects (binds) to LDAP server."""
        ldap3.set_config_parameter('RESTARTABLE_TRIES', 3)
        ldap3.set_config_parameter('DEFAULT_CLIENT_ENCODING', 'utf8')
        ldap3.set_config_parameter('DEFAULT_SERVER_ENCODING', 'utf8')
        for uri in self.uri:
            try:
                # Disable W0212: Access to a protected member _is_ipv6 of a
                #                client class
                #
                # This is needed because twisted monkey patches socket._is_ipv6
                # and ldap3 code is wrong.
                # pylint: disable=W0212
                ldap3.Server._is_ipv6 = lambda x, y: False
                server = ldap3.Server(uri, mode=ldap3.IP_V4_ONLY)
                if self.user and self.password:
                    self.ldap = ldap3.Connection(
                        server,
                        user=self.user,
                        password=self.password,
                        client_strategy=ldap3.RESTARTABLE,
                        auto_bind=True,
                        auto_encode=True,
                        auto_escape=True,
                        return_empty_attributes=False
                    )
                else:
                    self.ldap = ldap3.Connection(
                        server,
                        authentication=ldap3.SASL,
                        sasl_mechanism='GSSAPI',
                        client_strategy=ldap3.RESTARTABLE,
                        auto_bind=True,
                        auto_encode=True,
                        auto_escape=True,
                        return_empty_attributes=False
                    )
            except (ldap_exceptions.LDAPSocketOpenError,
                    ldap_exceptions.LDAPBindError,
                    ldap_exceptions.LDAPMaximumRetriesError):
                _LOGGER.debug('Could not connect to %s', uri, exc_info=True)
            else:
                break

        # E0704: The raise statement is not inside an except clause
        if not self.ldap:
            raise  # pylint: disable=E0704

    def search(self, search_base, search_filter,
               search_scope=ldap3.SUBTREE, attributes=None):
        """Call ldap search and return a generator of dn, entry tuples.
        """
        self.ldap.result = None
        self.ldap.search(
            search_base=search_base,
            search_filter=search_filter,
            search_scope=search_scope,
            attributes=attributes,
            dereference_aliases=ldap3.DEREF_NEVER
        )
        self._test_raise_exceptions()

        for entry in self.ldap.response:
            yield entry['dn'], _dict_normalize(entry['attributes'])

    def paged_search(self, search_base, search_filter,
                     search_scope=ldap3.SUBTREE, attributes=None):
        """Call ldap paged search and return a generator of dn, entry tuples.
        """
        self.ldap.result = None
        res_gen = self.ldap.extend.standard.paged_search(
            search_base=search_base,
            search_filter=search_filter,
            search_scope=search_scope,
            attributes=attributes,
            dereference_aliases=ldap3.DEREF_NEVER,
            paged_size=50,
            paged_criticality=True,
            generator=True
        )
        self._test_raise_exceptions()

        for entry in res_gen:
            yield entry['dn'], _dict_normalize(entry['attributes'])

    def _test_raise_exceptions(self):
        """
        Looks for specific error conditions or throws if non-success state.
        """
        if not self.ldap.result or 'result' not in self.ldap.result:
            return

        exception_type = None
        result_code = self.ldap.result['result']
        if result_code == 68:
            exception_type = ldap_exceptions.LDAPEntryAlreadyExistsResult
        elif result_code == 32:
            exception_type = ldap_exceptions.LDAPNoSuchObjectResult
        elif result_code == 50:
            exception_type =\
                ldap_exceptions.LDAPInsufficientAccessRightsResult
        elif result_code != 0:
            exception_type = ldap_exceptions.LDAPOperationResult

        if exception_type:
            raise exception_type(result=self.ldap.result['result'],
                                 description=self.ldap.result['description'],
                                 dn=self.ldap.result['dn'],
                                 message=self.ldap.result['message'],
                                 response_type=self.ldap.result['type'])

    def modify(self, dn, changes):
        """Call ldap modify and raise exception on non-success."""
        if changes:
            self.ldap.modify(dn, changes)
            self._test_raise_exceptions()

    def add(self, dn, object_class=None, attributes=None):
        """Call ldap add and raise exception on non-success."""
        sorted_attributes = collections.OrderedDict(sorted(
            (k, v)
            for k, v in six.iteritems(attributes)
        )) if attributes else None
        self.ldap.add(dn, object_class, sorted_attributes)
        self._test_raise_exceptions()

    def delete(self, dn):
        """Call ldap delete and raise exception on non-success."""
        self.ldap.delete(dn)
        self._test_raise_exceptions()

    def list(self, root=None):
        """Lists all objects in the database."""
        if not root:
            root = self.root_ou
        result = self.paged_search(
            search_base=root,
            search_filter='(objectClass=*)'
        )
        return [dn for dn, _ in result]

    def schema(self, abstract=True):
        """Get schema."""
        # Disable too many branches warning.
        #
        # pylint: disable=R0912
        #
        # NOTE: cn=schema,cn=config does *NOT* support paged searches.
        result = self.search(search_base='cn=schema,cn=config',
                             search_filter='(cn={*}treadmill)',
                             search_scope=ldap3.LEVEL,
                             attributes=['olcAttributeTypes',
                                         'olcObjectClasses'])

        try:
            schema_dn, entry = next(result)
        except StopIteration:
            return None

        attr_types = []
        for attr_type_s in entry.get('olcAttributeTypes', []):
            # Split preserving quotes.
            attr_type_l = shlex.split(attr_type_s)
            # Remove leading and closing bracket.
            attr_type_l = attr_type_l[1:-1]
            oid = attr_type_l.pop(0)
            assert oid.startswith(_TREADMILL_ATTR_OID_PREFIX)

            # Extract index: the last number in OID
            # (assuming that custom OID hierarchy has only 1 level)
            attr = {'oid': oid, 'idx': int(oid.split('.')[-1])}

            # Remaining are key/value pairs. Iterate over each, converting
            # key to lowercase.
            while attr_type_l:
                token = attr_type_l.pop(0)
                if token == 'NAME':
                    attr['name'] = attr_type_l.pop(0)
                if token == 'SYNTAX':
                    attr['syntax'] = attr_type_l.pop(0)
                elif token == 'DESC':
                    attr['desc'] = attr_type_l.pop(0)
                elif token == 'ORDERING':
                    attr['ordering'] = attr_type_l.pop(0)
                elif token == 'SUBSTR':
                    attr['substr'] = attr_type_l.pop(0)
                elif token == 'EQUALITY':
                    attr['equality'] = attr_type_l.pop(0)
                elif token == 'SINGLE-VALUE':
                    attr['single_value'] = True
                elif token == 'COLLECTIVE':
                    attr['collective'] = True
                elif token == 'OBSOLETE':
                    attr['obsolete'] = True
                else:
                    assert 'Unsupported token: %s: %s' % (attr_type_s, token)

            attr_types.append(attr)

        obj_classes = []

        def _parse_attr_list(alist):
            """Parses ( a $ b ) => [a, b]"""
            result = []
            assert alist.pop(0) == '('
            while len(alist) > 1:
                result.append(alist.pop(0))
                sep = alist.pop(0)
                if sep == ')':
                    return result
                assert sep == '$'

        for obj_cls_s in entry.get('olcObjectClasses', []):
            # Split preserving quotes.
            obj_cls_l = shlex.split(obj_cls_s)
            # Remove leading and closing bracket.
            obj_cls_l = obj_cls_l[1:-1]
            oid = obj_cls_l.pop(0)

            # Extract index: the last number in OID
            # (assuming that custom OID hierarchy has only 1 level)
            obj_cls = {'oid': oid, 'idx': int(oid.split('.')[-1])}

            # poor man parsing.
            while obj_cls_l:
                token = obj_cls_l.pop(0)
                if token == 'NAME':
                    obj_cls['name'] = obj_cls_l.pop(0)
                elif token == 'DESC':
                    obj_cls['desc'] = obj_cls_l.pop(0)
                elif token == 'SUP':
                    assert obj_cls_l.pop(0) == 'top'
                elif token == 'STRUCTURAL':
                    continue
                elif token == 'MUST':
                    obj_cls['must'] = _parse_attr_list(obj_cls_l)
                elif token == 'MAY':
                    obj_cls['may'] = _parse_attr_list(obj_cls_l)
                else:
                    assert 'Invalid token: %s, %r' % (obj_cls_s, token)

                obj_classes.append(obj_cls)

        if abstract:
            attr_types = dict([_attrtype_2_abstract(a) for a in attr_types])
            obj_classes = dict([_objcls_2_abstract(o) for o in obj_classes])

        return {'dn': schema_dn,
                'attributeTypes': attr_types,
                'objectClasses': obj_classes}

    @staticmethod
    def _schema_attrtype_diff(old_attr_types, new_attr_types):
        """Construct difference between old/new attr type list."""
        to_add = dict()
        to_del = dict()

        common = set(new_attr_types.keys()) & set(old_attr_types.keys())
        added = set(new_attr_types.keys()) - set(old_attr_types.keys())

        for name in common:
            old_attr = old_attr_types[name]
            new_attr = new_attr_types[name]

            for key in ['type', 'ignore_case']:
                if new_attr.get(key) != old_attr.get(key):
                    assert 'Type modified in place: %s' % name
            for key in ['desc']:
                if new_attr.get(key) != old_attr.get(key):
                    new_attr['idx'] = old_attr['idx']
                    to_del[name] = old_attr
                    to_add[name] = new_attr

        # Calculate max oid index.
        if not old_attr_types:
            next_oid = 1
        else:
            next_oid = max([attr['idx']
                            for attr in old_attr_types.values()]) + 1

        for name in added:
            attr = new_attr_types[name]
            attr['idx'] = next_oid
            next_oid += 1
            to_add[name] = attr

        return to_del, to_add

    @staticmethod
    def _schema_objcls_diff(old_ocs, new_ocs):
        """Construct difference between old/new attr type list."""
        to_add = dict()
        to_del = dict()

        common = set(new_ocs.keys()) & set(old_ocs.keys())
        added = set(new_ocs.keys()) - set(old_ocs.keys())

        for name in common:
            old_oc = old_ocs[name]
            new_oc = new_ocs[name]
            old_oc['name'] = name
            new_oc['name'] = name

            new_oc['idx'] = old_oc['idx']

            if _objcls_2_str(name, old_oc) != _objcls_2_str(name, new_oc):
                to_del[name] = old_oc
                to_add[name] = new_oc

        # Calculate max oid index.
        if not old_ocs:
            next_oid = 1
        else:
            next_oid = 1 + max([
                item['idx']
                for item in old_ocs.values()
            ])

        for name in added:
            objcls = new_ocs[name]
            objcls['idx'] = next_oid
            next_oid += 1
            to_add[name] = objcls

        return to_del, to_add

    def update_schema(self, new_schema):
        """Safely update schema, preserving existing attribute types."""
        old_schema = self.schema() or self.init_schema()

        schema_dn = old_schema['dn']
        old_attr_types = old_schema['attributeTypes']
        new_attr_types = new_schema['attributeTypes']

        changes = collections.defaultdict(list)
        to_del, to_add = self._schema_attrtype_diff(old_attr_types,
                                                    new_attr_types)

        if to_del:
            values = [_attrtype_2_str(_abstract_2_attrtype(name, attr))
                      for name, attr in six.iteritems(to_del)]
            _LOGGER.debug('del: %s - olcAttributeTypes: %r', schema_dn, values)
            changes['olcAttributeTypes'].extend(
                [(ldap3.MODIFY_DELETE, values)])

        if to_add:
            values = [_attrtype_2_str(_abstract_2_attrtype(name, attr))
                      for name, attr in six.iteritems(to_add)]
            _LOGGER.debug('add: %s - olcAttributeTypes: %r', schema_dn, values)
            changes['olcAttributeTypes'].extend([(ldap3.MODIFY_ADD, values)])

        old_obj_classes = old_schema['objectClasses']
        new_obj_classes = new_schema['objectClasses']

        to_del, to_add = self._schema_objcls_diff(old_obj_classes,
                                                  new_obj_classes)
        if to_del:
            values = [_objcls_2_str(name, item)
                      for name, item in six.iteritems(to_del)]
            _LOGGER.debug('del: %s - olcObjectClasses: %r', schema_dn, values)
            changes['olcObjectClasses'].extend([(ldap3.MODIFY_DELETE, values)])
        if to_add:
            values = [_objcls_2_str(name, item)
                      for name, item in six.iteritems(to_add)]
            _LOGGER.debug('add: %s - olcObjectClasses: %r', schema_dn, values)
            changes['olcObjectClasses'].extend([(ldap3.MODIFY_ADD, values)])

        if changes:
            self.modify(schema_dn, changes)
        else:
            _LOGGER.info('Schema is up to date.')

    def init_schema(self):
        """Initializes treadmill ldap schema namespace."""
        schema_dn = 'cn=treadmill,cn=schema,cn=config'
        schema_object_class = 'olcSchemaConfig'
        schema_attributes = {'cn': 'treadmill'}
        _LOGGER.debug('Creating: %s %s %s',
                      schema_dn, schema_object_class, schema_attributes)
        self.add(schema_dn, schema_object_class, schema_attributes)
        return self.schema()

    def init(self):
        """Initializes treadmill ldap namespace."""

        # TOOD: not sure if this takes into account more tnan 2 levels in
        #       ldap_suffix, e.g. dc=x,dc=y,dc=com
        dc = self.ldap_suffix.split(',')[0].split('=')[1]

        def _build_ou(ou, name=None):
            """Helper to build an ou string."""
            return 'ou=' + ou + ',' + self.root_ou, \
                   ['organizationalUnit'], \
                   {'ou': name or ou}

        dir_entries = [
            (self.ldap_suffix,
             ['dcObject', 'organization'],
             {'o': [dc], 'dc': [dc]}),
            (self.root_ou,
             ['organizationalUnit'],
             {'ou': self.root_ou}),
            _build_ou('apps', 'applications'),
            _build_ou('cells'),
            _build_ou('dns-servers'),
            _build_ou('servers'),
            _build_ou('tenants'),
            _build_ou('allocations'),
            _build_ou('app-groups'),
        ]

        for dn, object_class, attributes in dir_entries:
            try:
                _LOGGER.debug('Creating: %s %s %s',
                              dn, object_class, attributes)
                self.add(dn, object_class, attributes)
            except ldap_exceptions.LDAPEntryAlreadyExistsResult:
                _LOGGER.debug('%s already exists.', dn)

    def get(self, dn, query, attrs, paged_search=True):
        """Gets LDAP object given dn."""
        if paged_search:
            search_func = self.paged_search
        else:
            search_func = self.search

        result = search_func(search_base=dn,
                             search_filter=six.text_type(query),
                             search_scope=ldap3.BASE,
                             attributes=attrs)

        for _dn, entry in result:
            return entry

        return None

    def create(self, dn, entry):
        """Creates LDAP record."""
        _LOGGER.debug('create: %s - %s', dn, entry)
        self.add(dn, attributes=entry)

    def replace(self, dn, entry):
        """Replace content of the existing dn with new values."""
        _LOGGER.debug('replace: %s - %s', dn, entry)
        self.delete(dn)
        self.add(dn, attributes=entry)

    def update(self, dn, new_entry):
        """Creates LDAP record."""
        _LOGGER.debug('update: %s - %s', dn, new_entry)
        old_entry = self.get(dn, '(objectClass=*)', new_entry.keys())
        diff = _diff_entries(old_entry, new_entry)

        self.modify(dn, diff)

    def remove(self, dn, entry):
        """Removes attributes from the record."""
        to_be_removed = {
            k: [(ldap3.MODIFY_DELETE, [])] for k in entry.keys()
        }
        self.modify(dn, to_be_removed)

    def get_repls(self):
        """Get replication information."""
        # paged_search does not work with config backend, so using low level
        # search instead of higher level wrappers.
        result = self.search(
            search_base='olcDatabase={1}mdb,cn=config',
            search_filter='(objectclass=olcMdbConfig)',
            attributes=['olcSyncrepl'],
            search_scope=ldap3.BASE,
        )
        for _dn, entry in result:
            return entry.get('olcSyncrepl')


class LdapObject(object):
    """Ldap object base class.
    """
    # Allow such names as 'dn', 'ou'
    # pylint: disable=invalid-name

    def __init__(self, admin):
        self.admin = admin

    def from_entry(self, entry, _dn=None):
        """Converts ldap entry to dict."""
        return _entry_2_dict(entry, self.schema())

    def to_entry(self, obj):
        """Converts object to LDAP entry."""
        return _dict_2_entry(obj, self.schema())

    def attrs(self):
        """Returns list of object attributes."""
        return [ldap_field for ldap_field, _, _, in self.schema()]

    def _query(self):
        """Default query object."""
        return AndQuery('objectClass', self.oc())

    def dn(self, ident=None):
        """Object dn."""
        if ident:
            dn = self.admin.dn(['%s=%s' % (self.entity(), ident),
                                'ou=%s' % self.ou()])
        else:
            dn = self.admin.dn(['ou=%s' % self.ou()])

        return dn

    def get(self, ident):
        """Gets object given identity."""
        entry = self.admin.get(self.dn(ident),
                               self._query(),
                               self.attrs())
        if entry:
            return self.from_entry(entry, self.dn(ident))
        else:
            return None

    def create(self, ident, attrs):
        """Create new ldap record."""
        entry = _remove_empty(self.to_entry(attrs))
        if isinstance(ident, list):
            ident_attr = ident
        else:
            ident_attr = [six.text_type(ident)]

        entry.update({'objectClass': [self.oc()],
                      self.entity(): ident_attr})

        self.admin.create(self.dn(ident), entry)

    def list(self, attrs, generator=False):
        """List records, given attribute filter."""
        query = self._query()
        for ldap_field, obj_field, _field_type in self.schema():
            if obj_field not in attrs:
                continue

            if attrs[obj_field] is None:
                continue

            arg = ldap_field
            if isinstance(attrs[obj_field], list):
                for value in attrs[obj_field]:
                    query(arg, value)
            else:
                query(arg, attrs[obj_field])

        _LOGGER.debug('Query: %s', query.to_str())
        result = self.admin.paged_search(search_base=self.dn(),
                                         search_filter=query.to_str(),
                                         search_scope=ldap3.SUBTREE,
                                         attributes=self.attrs())
        if generator:
            return (self.from_entry(entry, dn) for dn, entry in result)
        return [self.from_entry(entry, dn) for dn, entry in result]

    def update(self, ident, attrs):
        """Updates LDAP record."""
        dn = self.dn(ident)
        new_entry = self.to_entry(attrs)
        self.admin.update(dn, new_entry)

    def replace(self, ident, attrs):
        """Replaces LDAP record."""
        self.delete(ident)
        self.create(ident, attrs)

    def remove(self, ident, attrs):
        """Updates LDAP record."""
        dn = self.dn(ident)
        new_entry = self.to_entry(attrs)
        self.admin.remove(dn, new_entry)

    def delete(self, ident):
        """Deletes LDAP record."""
        assert ident is not None
        self.admin.delete(self.dn(ident))

    def children(self, ident, clazz):
        """Selects all children given the children type."""
        dn = self.dn(ident)

        children_admin = clazz(self.admin)
        attrs = [elem[0] for elem in children_admin.schema()]
        search = self.admin.paged_search(
            search_base=dn,
            search_filter='(objectclass=%s)' % clazz.oc(),
            attributes=attrs
        )
        return [
            children_admin.from_entry(entry, child_dn)
            for child_dn, entry in search
        ]


class Server(LdapObject):
    """Server object."""

    _schema = [
        ('server', '_id', str),
        ('cell', 'cell', str),
        ('trait', 'traits', [str]),
        ('partition', 'partition', str),
        ('data', 'data', dict),
    ]

    _oc = 'tmServer'
    _ou = 'servers'
    _entity = 'server'

    def from_entry(self, entry, dn=None):
        """Converts LDAP app object to dict."""
        obj = super(Server, self).from_entry(entry, dn)

        if 'partition' not in obj:
            obj['partition'] = DEFAULT_PARTITION

        return obj


Server.schema = staticmethod(lambda: Server._schema)  # pylint: disable=W0212
Server.oc = staticmethod(lambda: Server._oc)  # pylint: disable=W0212
Server.ou = staticmethod(lambda: Server._ou)  # pylint: disable=W0212
Server.entity = staticmethod(lambda: Server._entity)  # pylint: disable=W0212


class DNS(LdapObject):
    """DNS object."""

    _schema = [('dns', '_id', str),
               ('server', 'server', [str]),
               ('location', 'location', str),
               ('rest-server', 'rest-server', [str]),
               ('zkurl', 'zkurl', str),
               ('fqdn', 'fqdn', str),
               ('ttl', 'ttl', str),
               ('nameservers', 'nameservers', [str])]

    _oc = 'tmDNS'
    _ou = 'dns-servers'
    _entity = 'dns'


DNS.schema = staticmethod(lambda: DNS._schema)  # pylint: disable=W0212
DNS.oc = staticmethod(lambda: DNS._oc)  # pylint: disable=W0212
DNS.ou = staticmethod(lambda: DNS._ou)  # pylint: disable=W0212
DNS.entity = staticmethod(lambda: DNS._entity)  # pylint: disable=W0212


class AppGroup(LdapObject):
    """AppGroup object."""

    _schema = [('app-group', '_id', str),
               ('group-type', 'group-type', str),
               ('cell', 'cells', [str]),
               ('pattern', 'pattern', str),
               ('endpoint-name', 'endpoints', [str]),
               ('data', 'data', [str])]

    _oc = 'tmAppGroup'
    _ou = 'app-groups'
    _entity = 'app-group'

    # W0221: Arguments number differs from overridden 'get'
    def get(self, ident, group_type=None):  # pylint: disable=W0221
        """Gets object given identity and group_type"""
        search = {'_id': ident}
        if group_type:
            search['group-type'] = group_type

        entries = self.list(search)
        if not entries:
            raise ldap_exceptions.LDAPNoSuchObjectResult(
                'No entries for {0} and group-type {1}'.format(
                    ident, group_type)
            )

        return entries[0]


AppGroup.schema = staticmethod(
    lambda: AppGroup._schema  # pylint: disable=W0212
)
AppGroup.oc = staticmethod(lambda: AppGroup._oc)  # pylint: disable=W0212
AppGroup.ou = staticmethod(lambda: AppGroup._ou)  # pylint: disable=W0212
AppGroup.entity = staticmethod(
    lambda: AppGroup._entity  # pylint: disable=W0212
)


class Application(LdapObject):
    """Application object."""

    @staticmethod
    def _services(app_obj, ldap_entry):
        """Populates services from ldap_entry."""

    _schema = [
        ('app', '_id', str),
        ('cpu', 'cpu', str),
        ('memory', 'memory', str),
        ('disk', 'disk', str),
        ('image', 'image', str),
        ('command', 'command', str),
        ('args', 'args', [str]),
        ('ticket', 'tickets', [str]),
        ('feature', 'features', [str]),
        ('identity-group', 'identity_group', str),
        ('shared-ip', 'shared_ip', bool),
        ('shared-network', 'shared_network', bool),
        ('passthrough', 'passthrough', [str]),
        ('schedule-once', 'schedule_once', bool),
        ('ephemeral-ports-tcp', 'ephemeral_ports_tcp', int),
        ('ephemeral-ports-udp', 'ephemeral_ports_udp', int),
        ('data-retention-timeout', 'data_retention_timeout', str),
        ('lease', 'lease', str),
    ]

    _svc_schema = [
        ('service-name', 'name', str),
        ('service-command', 'command', str),
        ('service-root', 'root', bool),
    ]

    _svc_restart_schema = [
        ('service-name', 'name', str),
        ('service-restart-limit', 'limit', int),
        ('service-restart-interval', 'interval', int),
    ]

    _default_svc_restart = {
        'limit': 5, 'interval': 60,
    }

    _endpoint_schema = [
        ('endpoint-name', 'name', str),
        ('endpoint-port', 'port', int),
        ('endpoint-proto', 'proto', str),
        ('endpoint-type', 'type', str),
    ]

    _environ_schema = [
        ('envvar-name', 'name', str),
        ('envvar-value', 'value', str),
    ]

    _affinity_schema = [
        ('affinity-level', 'level', str),
        ('affinity-limit', 'limit', int),
    ]

    _vring_schema = [
        ('vring-cell', 'cells', [str]),
    ]

    _vring_rule_schema = [
        ('vring-rule-endpoint', 'endpoints', [str]),
        ('vring-rule-pattern', 'pattern', str),
    ]

    _oc = 'tmApp'
    _ou = 'apps'
    _entity = 'app'

    @staticmethod
    def schema():
        """Returns combined schema for retrieval."""
        def _name_only(schema_rec):
            return (schema_rec[0], None, None)

        return sum(
            [
                [_name_only(e) for e in Application._svc_schema],
                [_name_only(e) for e in Application._svc_restart_schema],
                [_name_only(e) for e in Application._endpoint_schema],
                [_name_only(e) for e in Application._environ_schema],
                [_name_only(e) for e in Application._affinity_schema],
                [_name_only(e) for e in Application._vring_schema],
                [_name_only(e) for e in Application._vring_rule_schema],
            ],
            Application._schema
        )

    def from_entry(self, entry, dn=None):
        """Converts LDAP app object to dict."""
        obj = super(Application, self).from_entry(entry, dn)
        grouped = _group_entry_by_opt(entry)
        services = _grouped_to_list_of_dict(
            grouped, 'tm-service-', Application._svc_schema)
        service_restarts = _grouped_to_list_of_dict(
            grouped, 'tm-service-', Application._svc_restart_schema)
        endpoints = _grouped_to_list_of_dict(
            grouped, 'tm-endpoint-', Application._endpoint_schema)
        environ = _grouped_to_list_of_dict(
            grouped, 'tm-envvar-', Application._environ_schema)
        affinity_limits = _grouped_to_list_of_dict(
            grouped, 'tm-affinity-', Application._affinity_schema)
        vring_rules = _grouped_to_list_of_dict(
            grouped, 'tm-vring-rule-', Application._vring_rule_schema)

        obj['ephemeral_ports'] = {}
        if 'ephemeral_ports_tcp' in obj:
            obj['ephemeral_ports']['tcp'] = obj['ephemeral_ports_tcp']
            del obj['ephemeral_ports_tcp']
        if 'ephemeral_ports_udp' in obj:
            obj['ephemeral_ports']['udp'] = obj['ephemeral_ports_udp']
            del obj['ephemeral_ports_udp']

        # Merge services and services restarts
        for service in services:
            for service_restart in service_restarts:
                if service_restart['name'] == service['name']:
                    service['restart'] = {
                        'limit': service_restart['limit'],
                        'interval': service_restart['interval'],
                    }

        affinity_limits = {affinity['level']: affinity['limit']
                           for affinity in affinity_limits}

        vring = _entry_2_dict(entry, Application._vring_schema)
        vring['rules'] = vring_rules

        obj.update({
            'services': services,
            'endpoints': endpoints,
            'environ': environ,
            'affinity_limits': affinity_limits,
        })

        if vring['cells'] or vring['rules']:
            obj['vring'] = vring

        return obj

    def to_entry(self, obj):
        """Converts app dictionary to LDAP entry."""
        if 'ephemeral_ports' in obj:
            obj['ephemeral_ports_tcp'] = obj['ephemeral_ports'].get('tcp', 0)
            obj['ephemeral_ports_udp'] = obj['ephemeral_ports'].get('udp', 0)

        entry = super(Application, self).to_entry(obj)

        # Clean up
        if 'ephemeral_ports_tcp' in obj:
            del obj['ephemeral_ports_tcp']
        if 'ephemeral_ports_udp' in obj:
            del obj['ephemeral_ports_udp']

        for service in obj.get('services', []):
            service_entry = _dict_2_entry(
                service,
                Application._svc_schema,
                'tm-service',
                service['name']
            )
            # Account for default restart settings
            service_restart = self._default_svc_restart.copy()
            service_restart.update(
                service.get('restart', {})
            )
            service_entry.update(
                _dict_2_entry(
                    service_restart,
                    Application._svc_restart_schema,
                    'tm-service',
                    service['name']
                )
            )
            entry.update(service_entry)

        for endpoint in obj.get('endpoints', []):
            endpoint_entry = _dict_2_entry(endpoint,
                                           Application._endpoint_schema,
                                           'tm-endpoint',
                                           endpoint['name'])
            entry.update(endpoint_entry)

        for envvar in obj.get('environ', []):
            environ_entry = _dict_2_entry(envvar,
                                          Application._environ_schema,
                                          'tm-envvar',
                                          envvar['name'])
            entry.update(environ_entry)

        aff_lim = [{'level': aff, 'limit': obj['affinity_limits'][aff]}
                   for aff in obj.get('affinity_limits', {})]

        for limit in aff_lim:
            aff_lim_entry = _dict_2_entry(limit,
                                          Application._affinity_schema,
                                          'tm-affinity',
                                          limit['level'])

            entry.update(aff_lim_entry)

        vring = obj.get('vring')
        if vring:
            entry.update(_dict_2_entry(vring, Application._vring_schema))
            for rule in vring.get('rules', []):
                entry.update(_dict_2_entry(rule,
                                           Application._vring_rule_schema,
                                           'tm-vring-rule',
                                           rule['pattern']))

        return entry


Application.oc = staticmethod(lambda: Application._oc)  # pylint: disable=W0212
Application.ou = staticmethod(lambda: Application._ou)  # pylint: disable=W0212
Application.entity = staticmethod(
    lambda: Application._entity  # pylint: disable=W0212
)


class Cell(LdapObject):
    """Cell object."""
    _master_host_schema = [
        ('master-idx', 'idx', int),
        ('master-hostname', 'hostname', str),
        ('master-zk-client-port', 'zk-client-port', int),
        ('master-zk-jmx-port', 'zk-jmx-port', int),
        ('master-zk-followers-port', 'zk-followers-port', int),
        ('master-zk-election-port', 'zk-election-port', int),
    ]

    _schema = [
        ('cell', '_id', str),
        ('archive-server', 'archive-server', str),
        ('archive-username', 'archive-username', str),
        ('location', 'location', str),
        ('ssq-namespace', 'ssq-namespace', str),
        ('username', 'username', str),
        ('version', 'version', str),
        ('root', 'root', str),
        ('data', 'data', dict),
        ('status', 'status', str),
    ]

    _oc = 'tmCell'
    _ou = 'cells'
    _entity = 'cell'

    @staticmethod
    def schema():
        """Returns combined schema for retrieval."""
        def _name_only(schema_rec):
            return (schema_rec[0], None, None)

        return (
            Cell._schema +
            [_name_only(e) for e in Cell._master_host_schema]
        )

    def get(self, ident):
        """Gets cell given primary key."""
        obj = super(Cell, self).get(ident)
        obj['partitions'] = self.partitions(ident)
        return obj

    def partitions(self, ident):
        """Retrieves all partitions for given cell."""
        return self.children(ident, Partition)

    def from_entry(self, entry, dn=None):
        """Converts LDAP app object to dict."""
        obj = super(Cell, self).from_entry(entry, dn)
        grouped = _group_entry_by_opt(entry)
        masters = _grouped_to_list_of_dict(
            grouped, 'tm-master-', Cell._master_host_schema)

        obj.update({
            'masters': masters,
        })

        return obj

    def to_entry(self, obj):
        """Converts app dictionary to LDAP entry."""
        entry = super(Cell, self).to_entry(obj)

        for master in obj.get('masters', []):
            master_entry = _dict_2_entry(master,
                                         Cell._master_host_schema,
                                         'tm-master',
                                         master['idx'])
            entry.update(master_entry)

        return entry

    def delete(self, ident):
        """Deletes LDAP record."""
        dn = self.dn(ident)
        cell_partitions = self.admin.paged_search(
            search_base=dn,
            search_filter='(objectclass=tmPartition)',
            attributes=[]
        )

        for dn, _entry in cell_partitions:
            self.admin.delete(dn)

        return super(Cell, self).delete(ident)


Cell.oc = staticmethod(lambda: Cell._oc)  # pylint: disable=W0212
Cell.ou = staticmethod(lambda: Cell._ou)  # pylint: disable=W0212
Cell.entity = staticmethod(lambda: Cell._entity)  # pylint: disable=W0212


class Tenant(LdapObject):
    """Tenant object."""
    _schema = [('tenant', 'tenant', str),
               ('system', 'systems', [int])]

    _oc = 'tmTenant'
    _ou = 'allocations'
    _entity = 'tenant'

    def dn(self, ident=None):
        """Object dn."""
        if not ident:
            return self.admin.dn(['ou=%s' % self.ou()])

        parts = ['%s=%s' % (self.entity(), part)
                 for part in reversed(ident.split(':'))]
        parts.append('ou=%s' % self.ou())
        return self.admin.dn(parts)

    @staticmethod
    def schema():
        """Returns combined schema for retrieval."""
        return Tenant._schema

    def from_entry(self, entry, dn=None):
        """Converts LDAP app object to dict."""
        obj = super(Tenant, self).from_entry(entry, dn)
        return obj

    def to_entry(self, obj):
        """Converts tenant dictionary to LDAP entry."""
        entry = super(Tenant, self).to_entry(obj)
        return entry

    def allocations(self, ident):
        """Return all tenant's allocations."""
        return self.children(ident, Allocation)

    def reservations(self, ident):
        """Return all tenant's reservations."""
        return self.children(ident, CellAllocation)


Tenant.oc = staticmethod(lambda: Tenant._oc)  # pylint: disable=W0212
Tenant.ou = staticmethod(lambda: Tenant._ou)  # pylint: disable=W0212
Tenant.entity = staticmethod(lambda: Tenant._entity)  # pylint: disable=W0212


def _allocation_dn_parts(ident):
    """Construct allocation dn parts."""
    tenant_id, allocation_name = tuple(ident.split('/')[:2])
    parts = ['%s=%s' % (Allocation.entity(), allocation_name)]
    parts.extend(['%s=%s' % (Tenant.entity(), part)
                  for part in reversed(tenant_id.split(':'))])
    parts.append('ou=%s' % Allocation.ou())
    return parts


def _dn2cellalloc_id(dn):  # pylint: disable=invalid-name
    """Converts cell allocation dn to full id.
    """
    if not dn.startswith('cell='):
        return None

    parts = dn.split(',')
    cell = parts.pop(0).split('=')[1]
    allocation = parts.pop(0).split('=')[1]

    tenants = ':'.join(reversed([part.split('=')[1] for part in parts
                                 if part.startswith('tenant=')]))
    return '%s/%s/%s' % (tenants, allocation, cell)


class CellAllocation(LdapObject):
    """Models allocation reservation in a given cell."""

    _schema = [
        ('cell', 'cell', str),
        ('cpu', 'cpu', str),
        ('memory', 'memory', str),
        ('disk', 'disk', str),
        ('max-utilization', 'max_utilization', str),
        ('rank', 'rank', int),
        ('rank-adjustment', 'rank_adjustment', int),
        ('trait', 'traits', [str]),
        ('partition', 'partition', str),
    ]

    _assign_schema = [
        ('pattern', 'pattern', str),
        ('priority', 'priority', int),
    ]

    _oc = 'tmCellAllocation'
    _ou = 'allocations'
    _entity = 'cell'

    @staticmethod
    def schema():
        """Returns combined schema for retrieval."""
        def _name_only(schema_rec):
            return (schema_rec[0], None, None)
        return (
            CellAllocation._schema +
            [_name_only(e) for e in CellAllocation._assign_schema]
        )

    def dn(self, ident=None):
        """Object dn."""
        if not ident:
            return self.admin.dn(['ou=%s' % self.ou()])

        cell = ident[0]
        alloc_id = ident[1]

        parts = ['%s=%s' % (self.entity(), cell)]
        parts.extend(_allocation_dn_parts(alloc_id))
        return self.admin.dn(parts)

    def from_entry(self, entry, dn=None):
        """Converts cell allocation object to dict."""
        obj = super(CellAllocation, self).from_entry(entry, dn)

        if dn:
            ident = _dn2cellalloc_id(dn)
            if ident:
                obj['_id'] = ident

        grouped = _group_entry_by_opt(entry)
        assignments = _grouped_to_list_of_dict(
            grouped, 'tm-alloc-assignment-', CellAllocation._assign_schema)

        obj.update({
            'assignments': assignments,
        })

        if 'cpu' not in obj:
            obj['cpu'] = '0%'
        if 'memory' not in obj:
            obj['memory'] = '0G'
        if 'disk' not in obj:
            obj['disk'] = '0G'

        if 'partition' not in obj:
            obj['partition'] = DEFAULT_PARTITION

        if 'max_utilization' in obj:
            obj['max_utilization'] = float(obj['max_utilization'])

        return obj

    def to_entry(self, obj):
        """Converts app dictionary to LDAP entry."""
        entry = super(CellAllocation, self).to_entry(obj)
        for assignment in obj.get('assignments', []):
            assign_entry = _dict_2_entry(assignment,
                                         CellAllocation._assign_schema,
                                         'tm-alloc-assignment',
                                         assignment['pattern'])
            entry.update(assign_entry)

        return entry


CellAllocation.oc = staticmethod(
    lambda: CellAllocation._oc  # pylint: disable=W0212
)
CellAllocation.ou = staticmethod(
    lambda: CellAllocation._ou  # pylint: disable=W0212
)
CellAllocation.entity = staticmethod(
    lambda: CellAllocation._entity  # pylint: disable=W0212
)


class Allocation(LdapObject):
    """Allocation object."""

    _schema = [
        ('allocation', '_id', str),
        ('environment', 'environment', str),
    ]

    _oc = 'tmAllocation'
    _ou = 'allocations'
    _entity = 'allocation'

    def dn(self, ident=None):
        """Object dn."""
        if not ident:
            return self.admin.dn(['ou=%s' % self.ou()])
        else:
            return self.admin.dn(_allocation_dn_parts(ident))

    @staticmethod
    def schema():
        """Returns combined schema for retrieval."""
        return Allocation._schema

    def get(self, ident):
        """Gets allocation given primary key."""
        obj = super(Allocation, self).get(ident)
        obj['reservations'] = self.reservations(ident)
        return obj

    def delete(self, ident):
        """Deletes LDAP record."""
        # TODO: need to delete cell allocations as well.
        dn = self.dn(ident)
        cell_allocs_search = self.admin.paged_search(
            search_base=dn,
            search_filter='(objectclass=tmCellAllocation)',
            attributes=[]
        )

        for dn, _entry in cell_allocs_search:
            self.admin.delete(dn)

        return super(Allocation, self).delete(ident)

    def reservations(self, ident):
        """Retrieves all reservations for given allocation."""
        return self.children(ident, CellAllocation)


Allocation.oc = staticmethod(lambda: Allocation._oc)  # pylint: disable=W0212
Allocation.ou = staticmethod(lambda: Allocation._ou)  # pylint: disable=W0212
Allocation.entity = staticmethod(
    lambda: Allocation._entity  # pylint: disable=W0212
)


def _dn2partition_id(dn):  # pylint: disable=invalid-name
    """Converts cell partition dn to full id."""
    parts = dn.split(',')
    partition = parts.pop(0).split('=')[1]
    cell = parts.pop(0).split('=')[1]

    return (cell, partition)


class Partition(LdapObject):
    """Partition object."""

    _schema = [
        ('partition', '_id', str),
        ('cpu', 'cpu', str),
        ('disk', 'disk', str),
        ('memory', 'memory', str),
        ('system', 'systems', [int]),
        ('down-threshold', 'down-threshold', int),
        ('reboot-schedule', 'reboot-schedule', str)
    ]

    _oc = 'tmPartition'
    _ou = 'cells'
    _entity = 'partition'

    def dn(self, ident=None):
        """Object dn."""
        if not ident:
            return self.admin.dn(['ou=%s' % self.ou()])

        partition = ident[0]
        cell = ident[1]

        parts = [
            '%s=%s' % ('partition', partition),
            '%s=%s' % (Cell.entity(), cell),
            'ou=%s' % Cell.ou(),
        ]
        return self.admin.dn(parts)

    def from_entry(self, entry, dn=None):
        """Converts cell allocation object to dict."""
        obj = super(Partition, self).from_entry(entry, dn)

        if dn:
            cell, partition = _dn2partition_id(dn)

            obj['partition'] = partition
            obj['cell'] = cell

        if 'cpu' not in obj:
            obj['cpu'] = '0%'
        if 'memory' not in obj:
            obj['memory'] = '0G'
        if 'disk' not in obj:
            obj['disk'] = '0G'

        return obj


Partition.schema = staticmethod(
    lambda: Partition._schema  # pylint: disable=W0212
)
Partition.oc = staticmethod(
    lambda: Partition._oc  # pylint: disable=W0212
)
Partition.ou = staticmethod(
    lambda: Partition._ou  # pylint: disable=W0212
)
Partition.entity = staticmethod(
    lambda: Partition._entity  # pylint: disable=W0212
)


class HAProxy(LdapObject):
    """HAProxy object."""

    _schema = [
        ('server', '_id', str),
        ('cell', 'cell', str),
    ]

    _oc = 'tmHAProxy'
    _ou = 'haproxies'
    _entity = 'server'


HAProxy.schema = staticmethod(lambda: HAProxy._schema)  # pylint: disable=W0212
HAProxy.oc = staticmethod(lambda: HAProxy._oc)  # pylint: disable=W0212
HAProxy.ou = staticmethod(lambda: HAProxy._ou)  # pylint: disable=W0212
HAProxy.entity = staticmethod(lambda: HAProxy._entity)  # pylint: disable=W0212
