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
import itertools
import logging
import shlex

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


def _to_bool(value):
    """Fuzzy converion of string/int to bool."""
    if isinstance(value, bool):
        return value

    # XXX: This is necessary until previous bad entries are aacleaned up.
    _LOGGER.warning('Deprecation warning: bool as str')
    s_value = str(value).lower()
    if s_value in ('0', 'false'):
        return False
    else:
        return True


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
            obj[obj_field] = _to_bool(value[0])
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


def _dict_2_entry(obj, schema, option=None, option_idx=None):
    """Converts dict to ldap entry."""
    # TODO: refactor to eliminate too many branches warning.
    #
    # pylint: disable=R0912
    entry = dict()

    for ldap_field, obj_field, field_type in schema:
        if obj_field not in obj:
            continue

        value = obj[obj_field]
        if option is not None:
            assert option_idx is not None
            ldap_field = '{attribute};{option_prefix}-{option_idx:x}'.format(
                attribute=ldap_field,
                option_prefix=option,
                option_idx=option_idx
            )

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
                        _LOGGER.critical('Expected %r, got %r',
                                         field_type, value)
                    entry[ldap_field] = filtered
            elif field_type is bool:
                entry[ldap_field] = [_to_bool(value)]
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


def _empty_list_entry(schema):
    """Generate an empty list entry for the provided schema.
    """
    entry = {}
    for ldap_field, _obj_field, _field_type in schema:
        entry[ldap_field] = []

    return entry


def _to_obj_list(obj_list, key, prefix, schema):
    """Convert a (keyed) object list, into an entry.

    :param ``list`` obj_list:
        List of object
    :param ``str`` key:
        Key attribute in each object
    :param ``str`` prefix:
        LDAP attribute prefix (AttributeOption)
    :param schema:
        Object's schema
    """
    obj_iter = sorted(
        obj_list,
        key=lambda obj: obj[key]
    )
    if not obj_iter:
        entry = _empty_list_entry(schema)
    else:
        entry = {}
        for idx, obj in enumerate(obj_iter):
            entry.update(
                _dict_2_entry(
                    obj,
                    schema, prefix,
                    idx
                )
            )
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


def _entry_plain_keys(entry):
    """Return an entry keys, stripping all options.
    """
    return sorted({
        k.split(';', 1)[0]
        for k in entry.keys()
    })


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


class AndQuery:
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


class Admin:
    """Manages Treadmill objects in ldap.
    """
    # Allow such names as 'dn', 'ou'
    # pylint: disable=invalid-name
    # pylint: disable=too-many-statements

    def __init__(self, uri, ldap_suffix,
                 user=None, password=None, connect_timeout=5, write_uri=None):
        self.uri = uri
        self.write_uri = write_uri

        self.ldap_suffix = ldap_suffix
        self.root_ou = 'ou=treadmill,%s' % ldap_suffix
        self.user = user
        self.password = password
        self._connect_timeout = connect_timeout

        self.ldap = None
        self.write_ldap = None

    def close(self):
        """Closes ldap connection."""
        try:
            if self.ldap:
                self.ldap.unbind()
        except ldap_exceptions.LDAPCommunicationError:
            _LOGGER.exception('cannot close connection.')

        try:
            if self.write_ldap:
                self.write_ldap.unbind()
        except ldap_exceptions.LDAPCommunicationError:
            _LOGGER.exception('cannot close connection.')

    def dn(self, parts):
        """Constructs dn."""
        return ','.join(parts + [self.root_ou])

    def _connect_to_uri(self, uri):
        """Create an LDAP connection to the given URI."""
        try:
            server = ldap3.Server(
                uri,
                mode=ldap3.IP_V4_ONLY,
                connect_timeout=self._connect_timeout,
            )
            if self.user and self.password:
                ldap_auth = {
                    'user': self.user,
                    'password': self.password
                }
            else:
                ldap_auth = {
                    'authentication': ldap3.SASL,
                    'sasl_mechanism': 'GSSAPI'
                }

            return ldap3.Connection(
                server,
                client_strategy=ldap3.RESTARTABLE,
                auto_bind=True,
                auto_encode=True,
                auto_escape=True,
                return_empty_attributes=False,
                **ldap_auth
            )
        except (ldap_exceptions.LDAPSocketOpenError,
                ldap_exceptions.LDAPBindError,
                ldap_exceptions.LDAPMaximumRetriesError):
            _LOGGER.debug('Failed to connect to %s', uri, exc_info=True)
            return None

    def connect(self):
        """Connects (binds) to LDAP server."""
        ldap3.set_config_parameter('RESTARTABLE_TRIES', 3)
        ldap3.set_config_parameter('DEFAULT_CLIENT_ENCODING', 'utf8')
        ldap3.set_config_parameter('DEFAULT_SERVER_ENCODING', 'utf8')
        # This is needed because twisted monkey-patches socket._is_ipv6
        # and ldap3 code is wrong.
        # pylint: disable=protected-access
        ldap3.Server._is_ipv6 = lambda x, y: False

        if self.ldap or self.write_ldap:
            _LOGGER.debug('Closing existing connections before connect')
            self.close()

        for uri in self.uri:
            ldap_connection = self._connect_to_uri(uri)
            if ldap_connection is not None:
                self.ldap = ldap_connection
                break

        if not self.ldap:
            raise ldap_exceptions.LDAPBindError(
                'Failed to connect to any LDAP server: {}'.format(
                    ', '.join(self.uri)
                )
            )

        if not self.write_uri:
            self.write_ldap = self.ldap
            return

        for write_uri in self.write_uri:
            ldap_connection = self._connect_to_uri(write_uri)
            if ldap_connection is not None:
                self.write_ldap = ldap_connection
                break

        if not self.write_ldap:
            raise ldap_exceptions.LDAPBindError(
                'Failed to connect to any LDAP server: {}'.format(
                    ', '.join(self.write_uri)
                )
            )

    def search(self, search_base, search_filter,
               search_scope=ldap3.SUBTREE, attributes=None, dirty=False):
        """Call ldap search and return a generator of dn, entry tuples.
        """
        # If entries in the potential search results were written or modified
        # recently, we use the connection to the write server to avoid problems
        # with replication delays between provider and consumer
        ldap = self.write_ldap if dirty else self.ldap

        ldap.result = None
        ldap.search(
            search_base=search_base,
            search_filter=search_filter,
            search_scope=search_scope,
            attributes=attributes,
            dereference_aliases=ldap3.DEREF_NEVER
        )
        self._test_raise_exceptions(ldap)

        for entry in ldap.response:
            yield entry['dn'], entry['attributes']

    def paged_search(self, search_base, search_filter,
                     search_scope=ldap3.SUBTREE, attributes=None, dirty=False):
        """Call ldap paged search and return a generator of dn, entry tuples.
        """
        # If entries in the potential search results were written or modified
        # recently, we use the connection to the write server to avoid problems
        # with replication delays between provider and consumer
        ldap = self.write_ldap if dirty else self.ldap

        ldap.result = None
        res_gen = ldap.extend.standard.paged_search(
            search_base=search_base,
            search_filter=search_filter,
            search_scope=search_scope,
            attributes=attributes,
            dereference_aliases=ldap3.DEREF_NEVER,
            paged_size=50,
            paged_criticality=True,
            generator=True
        )
        self._test_raise_exceptions(ldap)

        for entry in res_gen:
            yield entry['dn'], entry['attributes']

    def _test_raise_exceptions(self, ldap=None):
        """
        Looks for specific error conditions or throws if non-success state.
        """
        if ldap is None:
            ldap = self.ldap

        if not ldap.result or 'result' not in ldap.result:
            return

        exception_type = None
        result_code = ldap.result['result']
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
            raise exception_type(result=ldap.result['result'],
                                 description=ldap.result['description'],
                                 dn=ldap.result['dn'],
                                 message=ldap.result['message'],
                                 response_type=ldap.result['type'])

    def modify(self, dn, changes):
        """Call ldap modify and raise exception on non-success."""
        if changes:
            self.write_ldap.modify(dn, changes)
            self._test_raise_exceptions(self.write_ldap)

    def add(self, dn, object_class=None, attributes=None):
        """Call ldap add and raise exception on non-success."""
        sorted_attributes = collections.OrderedDict(sorted(
            (k, v)
            for k, v in six.iteritems(attributes)
        )) if attributes else None
        self.write_ldap.add(dn, object_class, sorted_attributes)
        self._test_raise_exceptions(self.write_ldap)

    def delete(self, dn):
        """Call ldap delete and raise exception on non-success."""
        self.write_ldap.delete(dn)
        self._test_raise_exceptions(self.write_ldap)

    def list(self, root=None, dirty=False):
        """Lists all objects in the database."""
        if not root:
            root = self.root_ou
        result = self.paged_search(
            search_base=root,
            search_filter='(objectClass=*)',
            dirty=dirty
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
            attr_types = {
                name: abstract
                for (name, abstract) in (
                    _attrtype_2_abstract(a) for a in attr_types
                )
            }
            obj_classes = {
                name: abstract
                for (name, abstract) in (
                    _objcls_2_abstract(o) for o in obj_classes
                )
            }

        return {'dn': schema_dn,
                'attributeTypes': attr_types,
                'objectClasses': obj_classes}

    @staticmethod
    def _schema_attrtype_diff(old_attr_types, new_attr_types):
        """Construct difference between old/new attr type list.
        """
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
        """Construct difference between old/new attr type list.
        """
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
            # TODO must be modified in a specific order to avoid exceptions
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

    def get(self, dn, query, attrs, paged_search=True, dirty=False):
        """Gets LDAP object given dn."""
        if paged_search:
            search_func = self.paged_search
        else:
            search_func = self.search

        result = search_func(search_base=dn,
                             search_filter=six.text_type(query),
                             search_scope=ldap3.BASE,
                             attributes=attrs,
                             dirty=dirty)

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
        old_entry = self.get(
            dn,
            '(objectClass=*)',
            _entry_plain_keys(new_entry)
        )
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


class LdapObject:
    """Ldap object base class.
    """
    # Allow such names as 'dn', 'ou'
    # pylint: disable=invalid-name

    _operational_attrs = ['createTimestamp', 'modifyTimestamp']

    def __init__(self, admin):
        self.admin = admin

    def from_entry(self, entry, _dn=None):
        """Converts ldap entry to dict."""
        obj = _entry_2_dict(entry, self.schema())

        # Add operational attrs if they were requested, those can only be read.
        # create/modifyTimestamp are single-valued, UTC aware datetime objects.
        if entry.get('createTimestamp'):
            obj['_create_timestamp'] = entry['createTimestamp'].timestamp()
        if entry.get('modifyTimestamp'):
            obj['_modify_timestamp'] = entry['modifyTimestamp'].timestamp()
        return obj

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

    def get(self, ident, dirty=False, get_operational_attrs=False):
        """Gets object given identity."""
        attrs = self.attrs()
        if get_operational_attrs:
            attrs += self._operational_attrs
        entry = self.admin.get(
            self.dn(ident), self._query(), attrs, dirty=dirty,
        )
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

    def list(self, attrs, generator=False, dirty=False,
             get_operational_attrs=False):
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

        attributes = self.attrs()
        if get_operational_attrs:
            attributes += self._operational_attrs

        result = self.admin.paged_search(search_base=self.dn(),
                                         search_filter=query.to_str(),
                                         search_scope=ldap3.SUBTREE,
                                         attributes=attributes,
                                         dirty=dirty)
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

    def children(self, ident, clazz, dirty=False, extra_filters=None):
        """Selects all children given the children type."""
        dn = self.dn(ident)
        children_admin = clazz(self.admin)
        attrs = [elem[0] for elem in children_admin.schema()]
        filters = ["(objectclass={})".format(clazz.oc())]
        if extra_filters:
            filters.extend(extra_filters)
        search_filter = "(&{})".format(''.join(filters))
        children = self.admin.paged_search(
            search_base=dn,
            search_filter=search_filter,
            attributes=attrs,
            dirty=dirty
        )
        return [
            children_admin.from_entry(entry, child_dn)
            for child_dn, entry in children
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

    # pylint: disable=arguments-differ
    def get(self, ident, group_type=None, dirty=False,
            get_operational_attrs=False):
        """Gets object given identity and group_type"""
        entry = super(AppGroup, self).get(
            ident, dirty, get_operational_attrs=get_operational_attrs
        )
        if entry and group_type and entry['group-type'] != group_type:
            return None

        return entry


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
        ('trait', 'traits', [str]),
    ]

    _svc_schema = [
        ('service-name', 'name', str),
        ('service-command', 'command', str),
        ('service-image', 'image', str),
        ('service-useshell', 'useshell', bool),
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

        # FIXME: Service serialization is more complex because we do some
        # normalization in there which has no place in this function. Move the
        # "default restart" stuff and convert to use the _to_obj_list function.
        services_iter = sorted(
            obj.get('services', []),
            key=lambda service: service['name']
        )
        if not services_iter:
            entry.update(
                _empty_list_entry(
                    Application._svc_schema +
                    Application._svc_restart_schema
                )
            )
        else:
            for idx, service in enumerate(services_iter):
                service_entry = _dict_2_entry(
                    service,
                    Application._svc_schema,
                    'tm-service',
                    idx
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
                        idx
                    )
                )
                entry.update(service_entry)

        # Add endpoints
        entry.update(
            _to_obj_list(
                obj.get('endpoints', []),
                'name',
                'tm-endpoint',
                Application._endpoint_schema
            )
        )
        # Add environ variables
        entry.update(
            _to_obj_list(
                obj.get('environ', []),
                'name',
                'tm-envvar',
                Application._environ_schema,
            )
        )
        # Add affinity limits
        entry.update(
            _to_obj_list(
                [
                    {
                        'level': aff,
                        'limit': obj['affinity_limits'][aff]
                    }
                    for aff in obj.get('affinity_limits', {})
                ],
                'level',
                'tm-affinity',
                Application._affinity_schema,
            )
        )

        vring = obj.get('vring')
        if vring:
            entry.update(_dict_2_entry(vring, Application._vring_schema))
            entry.update(
                _to_obj_list(
                    vring.get('rules', []),
                    'pattern',
                    'tm-vring-rule',
                    Application._vring_rule_schema
                )
            )

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
        # TODO: archive-*, ssq-* - stale attributes.
        ('archive-server', 'archive-server', str),
        ('archive-username', 'archive-username', str),
        ('location', 'location', str),
        ('ssq-namespace', 'ssq-namespace', str),
        ('username', 'username', str),
        ('version', 'version', str),
        ('root', 'root', str),
        ('data', 'data', dict),
        ('status', 'status', str),
        ('trait', 'traits', [str]),
        ('zk-auth-scheme', 'zk-auth-scheme', str),
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

    def get(self, ident, dirty=False, get_operational_attrs=False):
        """Gets cell given primary key."""
        obj = super(Cell, self).get(
            ident, dirty=dirty, get_operational_attrs=get_operational_attrs
        )
        obj['partitions'] = self.partitions(ident, dirty=dirty)
        return obj

    def partitions(self, ident, dirty=False):
        """Retrieves all partitions for given cell."""
        return self.children(ident, Partition, dirty=dirty)

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
            entry.update(
                _dict_2_entry(
                    master,
                    Cell._master_host_schema,
                    'tm-master',
                    master['idx']
                )
            )

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

    def allocations(self, ident, dirty=False):
        """Return all tenant's allocations."""
        return self.children(ident,
                             Allocation,
                             dirty=dirty,
                             extra_filters=["(allocation={}/*)".format(ident)])

    def reservations(self, ident, dirty=False):
        """Return all tenant's reservations."""
        # TODO:
        # Traversing a tenant's and all its subtenants' CellAllocations
        # in LDAP, and then filtering out those belong to subtenats.
        # This is inefficient.
        # Need to find a better search_filter and/or search_scope in
        # LDAP searching to exlcude those subtenants,
        # namely to exclude some sub-RDN ('tenant=<subtenant name>').
        subtree_reservations = self.children(ident,
                                             CellAllocation,
                                             dirty=dirty)
        reservations_generator = filter(
            lambda reserv: reserv['_id'].startswith(ident + '/'),
            subtree_reservations
        )

        return list(reservations_generator)


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
        entry.update(
            _to_obj_list(
                obj.get('assignments', []),
                'pattern',
                'tm-alloc-assignment',
                CellAllocation._assign_schema,
            )
        )

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

    def get(self, ident, dirty=False, get_operational_attrs=False):
        """Gets allocation given primary key."""
        obj = super(Allocation, self).get(
            ident, dirty=dirty, get_operational_attrs=get_operational_attrs
        )
        obj['reservations'] = self.reservations(ident, dirty=dirty)
        return obj

    def delete(self, ident):
        """Deletes LDAP record."""
        dn = self.dn(ident)
        cell_allocs_search = self.admin.paged_search(
            search_base=dn,
            search_filter='(objectclass=tmCellAllocation)',
            attributes=[]
        )

        for dn, _entry in cell_allocs_search:
            self.admin.delete(dn)

        return super(Allocation, self).delete(ident)

    def reservations(self, ident, dirty=False):
        """Retrieves all reservations for given allocation."""
        return self.children(ident, CellAllocation, dirty=dirty)


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
        ('reboot-schedule', 'reboot-schedule', str),
        ('data', 'data', dict),
    ]

    _limit_schema = [
        ('allocation-limit-trait', 'trait', str),
        ('allocation-limit-cpu', 'cpu', str),
        ('allocation-limit-disk', 'disk', str),
        ('allocation-limit-memory', 'memory', str),
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

    @staticmethod
    def schema():
        """Returns combined schema for retrieval."""
        def _name_only(schema_rec):
            return (schema_rec[0], None, None)

        return (
            Partition._schema +
            [_name_only(e) for e in Partition._limit_schema]
        )

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

        grouped = _group_entry_by_opt(entry)
        limits = _grouped_to_list_of_dict(
            grouped, 'tm-alloc-limit-', Partition._limit_schema)

        obj.update({
            'limits': limits,
        })

        return obj

    def to_entry(self, obj):
        """Converts app dictionary to LDAP entry."""
        entry = super(Partition, self).to_entry(obj)

        entry.update(
            _to_obj_list(
                obj.get('limits', []),
                'trait',
                'tm-alloc-limit',
                Partition._limit_schema,
            )
        )

        return entry


Partition.oc = staticmethod(
    lambda: Partition._oc  # pylint: disable=W0212
)
Partition.ou = staticmethod(
    lambda: Partition._ou  # pylint: disable=W0212
)
Partition.entity = staticmethod(
    lambda: Partition._entity  # pylint: disable=W0212
)
