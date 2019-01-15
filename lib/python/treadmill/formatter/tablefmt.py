"""Table CLI formatter.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import time

import prettytable
import six

from treadmill import yamlwrapper as yaml


def fmt_time(timestamp):
    """Return ISO formatted time from seconds from epoch."""
    if timestamp:
        return time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(timestamp))
    else:
        return '-'


def fmt_utilization(util):
    """Format utilization."""
    return '{0:.4f}'.format(util)


def wrap_words(words, length, sep=',', newline='\n'):
    """Join words by sep, no more than count in each line."""
    lines = []
    line = []
    cur_length = 0
    while True:
        if not words:
            lines.append(line)
            break

        if cur_length + len(line) > length:
            lines.append(line)
            cur_length = 0
            line = []

        word = words.pop(0)
        cur_length += len(word)
        line.append(word)

    return newline.join([sep.join(line) for line in lines])


def make_wrap_words(length, sep=','):
    """Returng wrap words function."""
    return lambda words: wrap_words(words, length, sep)


def _make_table(columns, header=False, align=None):
    """Make a table object for output."""
    if not align:
        align = {}

    table = prettytable.PrettyTable(columns)
    for col in columns:
        table.align[col] = align.get(col, 'l')

    table.set_style(prettytable.PLAIN_COLUMNS)
    # For some reason, headers must be disable after set_style.
    table.header = header

    table.left_padding_width = 0
    table.right_padding_width = 2
    return table


def _cell(item, column, key, fmt):
    """Constructs a value in table cell."""
    if key is None:
        key = column

    if isinstance(key, six.string_types):
        keys = [key]
    else:
        keys = key

    raw_value = None
    for k in keys:
        if k in item and item[k] is not None:
            raw_value = item[k]
            break

    if callable(fmt):
        try:
            value = fmt(raw_value)
        except Exception:  # pylint: disable=W0703
            if raw_value is None:
                value = '-'
            else:
                raise
    else:
        if raw_value is None:
            value = '-'
        else:
            if isinstance(raw_value, list):
                value = ','.join(six.moves.map(str, raw_value))
            else:
                value = raw_value
    return value


def dict_to_table(item, schema, sortby=None):
    """Display object as table."""
    table = _make_table(['key', '', 'value'], header=False)
    for column, key, fmt in schema:
        value = _cell(item, column, key, fmt)
        table.add_row([column, ':', value])

    table.sortby = sortby
    return table


def make_dict_to_table(schema):
    """Return dict to table function given schema."""
    return lambda item: dict_to_table(item, schema)


def list_to_table(items, schema, header=True, align=None, sortby=None):
    """Display  list of items as table."""
    columns = [column for column, _, _ in schema]
    table = _make_table(columns, header=header, align=align)
    if items is None:
        items = []
    for item in items:
        row = []
        for column, key, fmt in schema:
            row.append(_cell(item, column, key, fmt))
        table.add_row(row)

    table.sortby = sortby
    return table


def make_list_to_table(schema, header=True, align=None):
    """Return list to table function given schema."""
    return lambda items: list_to_table(items, schema, header, align)


class AppPrettyFormatter:
    """Pretty table app formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""

        services_restart_tbl = make_dict_to_table([
            ('limit', None, None),
            ('interval', None, None),
        ])

        def _command_fmt(cmd):
            return wrap_words(cmd.split(), 40, ' ', '\n   ')

        services_tbl = make_list_to_table([
            ('name', None, None),
            ('root', None, None),
            ('restart', None, services_restart_tbl),
            ('command', None, _command_fmt),
            ('shell', 'useshell', None),
            ('image', None, None),
        ])

        endpoints_tbl = make_list_to_table([
            ('name', None, None),
            ('port', None, None),
            ('proto', None, lambda proto: proto if proto else 'tcp'),
            ('type', None, None),
        ])

        environ_tbl = make_list_to_table([
            ('name', None, None),
            ('value', None, None),
        ])

        vring_rules_tbl = make_list_to_table([
            ('pattern', None, None),
            ('endpoints', None, ','.join),
        ])

        vring_tbl = make_dict_to_table([
            ('cells', None, ','.join),
            ('rules', None, vring_rules_tbl),
        ])

        ephemeral_tbl = make_dict_to_table([
            ('tcp', None, None),
            ('udp', None, None),
        ])

        affinity_limits_tbl = make_dict_to_table([
            ('pod', None, None),
            ('rack', None, None),
            ('server', None, None),
        ])

        schema = [
            ('name', '_id', None),
            ('memory', None, None),
            ('cpu', None, None),
            ('disk', None, None),
            ('tickets', None, None),
            ('features', None, None),
            ('identity-group', 'identity_group', None),
            ('schedule-once', 'schedule_once', None),
            ('shared-ip', 'shared_ip', None),
            ('ephemeral-ports', 'ephemeral_ports', ephemeral_tbl),
            ('services', None, services_tbl),
            ('endpoints', None, endpoints_tbl),
            ('environ', None, environ_tbl),
            ('vring', None, vring_tbl),
            ('passthrough', None, '\n'.join),
            ('data-retention-timeout', 'data_retention_timeout', None),
            ('lease', 'lease', None),
            ('traits', 'traits', None),
            ('affinity', 'affinity', None),
            ('affinity-limits', 'affinity_limits', affinity_limits_tbl),
        ]

        format_item = make_dict_to_table(schema)

        format_list = make_list_to_table([
            ('name', '_id', None),
            ('memory', None, None),
            ('cpu', None, None),
            ('disk', None, None),
            ('tickets', None, None),
            ('features', None, None),
        ])

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)


class AppMonitorPrettyFormatter:
    """Pretty table app monitor formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        schema = [('monitor', '_id', None),
                  ('count', 'count', None),
                  ('policy', 'policy', None),
                  ('suspend until', 'suspend_until', fmt_time)]

        format_item = make_dict_to_table(schema)
        format_list = make_list_to_table(schema)

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)


class IdentityGroupPrettyFormatter:
    """Pretty table identity group formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        schema = [('identity-group', '_id', None),
                  ('count', 'count', None)]

        format_item = make_dict_to_table(schema)
        format_list = make_list_to_table(schema)

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)


class ServerPrettyFormatter:
    """Pretty table server formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""

        schema = [
            ('name', '_id', None),
            ('cell', None, None),
            ('traits', None, None),
            ('partition', None, None),
            ('data', None, None),
        ]

        format_item = make_dict_to_table(schema)
        format_list = make_list_to_table(schema)

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)


class ServerNodePrettyFormatter:
    """Pretty table server (scheduler) node formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        schema = [('name', None, None),
                  ('memory', None, None),
                  ('cpu', None, None),
                  ('disk', None, None),
                  ('partition', None, None),
                  ('parent', None, None),
                  ('traits', None, None),
                  ('state', None, None),
                  ('since', None, fmt_time)]

        format_item = make_dict_to_table(schema)
        format_list = make_list_to_table(schema)

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)


class LdapSchemaPrettyFormatter:
    """Pretty table ldap schema formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        attr_tbl = make_list_to_table([
            ('name', None, None),
            ('desc', None, None),
            ('type', None, None),
            ('ignore_case', None, None),
        ])

        objcls_tbl = make_list_to_table([
            ('name', None, None),
            ('desc', None, None),
            ('must', None, None),
            ('may', None, make_wrap_words(40)),
        ])

        schema_tbl = make_dict_to_table([
            ('dn', None, None),
            ('attributes', 'attributeTypes', attr_tbl),
            ('objects', 'objectClasses', objcls_tbl),
        ])

        return schema_tbl(item)


class BucketPrettyFormatter:
    """Pretty table bucket formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        schema = [('name', None, None),
                  ('parent', None, None),
                  ('traits', None, None)]

        format_item = make_dict_to_table(schema)
        format_list = make_list_to_table(schema)

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)


class CellPrettyFormatter:
    """Pretty table cell formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        masters_tbl = make_list_to_table([
            ('idx', None, None),
            ('hostname', None, None),
            ('zk-client-port', None, None),
            ('zk-jmx-port', None, None),
            ('zk-followers-port', None, None),
            ('zk-election-port', None, None),
        ])

        partitions_tbl = make_list_to_table([
            ('id', 'partition', None),
            ('cpu', None, None),
            ('disk', None, None),
            ('memory', None, None),
            ('system', 'systems', None),
            ('down threshold', 'down-threshold', None),
            ('reboot schedule', 'reboot-schedule', None),
        ])

        schema = [
            ('name', '_id', None),
            ('version', None, None),
            ('root', None, None),
            ('username', None, None),
            ('zk-auth-scheme', None, None),
            ('location', None, None),
            ('traits', None, None),
            ('masters', None, masters_tbl),
            ('partitions', None, partitions_tbl),
            ('data', None, yaml.dump),
        ]

        format_item = make_dict_to_table(schema)

        format_list = make_list_to_table([
            ('name', '_id', None),
            ('location', None, None),
            ('version', None, None),
            ('username', None, None),
            ('root', None, None),
            ('zk-auth-scheme', None, None),
        ])

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)


class DNSPrettyFormatter:
    """Pretty table critical DNS formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        schema = [('name', '_id', None),
                  ('location', None, None),
                  ('servers', 'server', '\n'.join),
                  ('rest-servers', 'rest-server', '\n'.join),
                  ('zkurl', None, None),
                  ('fqdn', None, None),
                  ('ttl', None, None),
                  ('nameservers', None, '\n'.join)]

        format_item = make_dict_to_table(schema)
        format_list = make_list_to_table([
            ('name', '_id', None),
            ('location', None, None),
            ('fqdn', None, None),
            ('servers', 'server', ','.join),
        ])

        if isinstance(item, list):
            return format_list(item)

        return format_item(item)


class AppGroupPrettyFormatter:
    """Pretty table App Groups formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        schema = [('name', '_id', None),
                  ('type', 'group-type', None),
                  ('cells', None, None),
                  ('pattern', None, None),
                  ('endpoints', None, None),
                  ('data', None, None)]

        format_item = make_dict_to_table(schema)
        format_list = make_list_to_table(schema)

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)


class TenantPrettyFormatter:
    """Pretty table tenant formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        schema = [
            ('tenant', ['_id', 'tenant'], None),
            ('system', 'systems', None),
        ]

        format_item = make_dict_to_table(
            schema +
            [('allocations', 'allocations', AllocationPrettyFormatter.format)]
        )
        format_list = make_list_to_table(schema)

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)


class AllocationPrettyFormatter:
    """Pretty table allocation formatter."""
    @staticmethod
    def format(item):
        """Return pretty-formatted item."""

        assignments_table = make_list_to_table([
            ('pattern', None, None),
            ('priority', None, None),
        ])

        cell_tbl = make_list_to_table([
            ('cell', 'cell', None),
            ('partition', None, None),
            ('rank', None, None),
            ('rank-adjustment', 'rank_adjustment', None),
            ('max-utilization', 'max_utilization', None),
            ('memory', None, None),
            ('cpu', None, None),
            ('disk', None, None),
            ('traits', None, None),
            ('assignments', None, assignments_table),
        ])

        schema = [
            ('name', '_id', None),
            ('environment', None, None),
            ('reservations', None, cell_tbl),
        ]

        format_item = make_dict_to_table(schema)
        format_list = make_list_to_table(schema)

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)


class InstanceStatePrettyFormatter:
    """Pretty table instance state formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        schema = [
            ('name', None, None),
            ('state', None, None),
            ('host', None, None),
        ]

        format_item = make_dict_to_table(schema)
        format_list = make_list_to_table(schema, header=False)

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)


class InstanceFinishedStatePrettyFormatter:
    """Pretty table instance finished state formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        schema = [
            ('name', None, None),
            ('state', None, None),
            ('host', None, None),
            ('when', None, None),
            ('details', None, None),
        ]

        format_item = make_dict_to_table(schema)
        format_list = make_list_to_table(schema, header=False)

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)


class EndpointPrettyFormatter:
    """Pretty table endpoint formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        def _fmt_state(state):
            """Format endpoint state."""
            return '-' if state is None else 'up' if state else 'down'

        schema = [
            ('name', None, None),
            ('proto', None, None),
            ('endpoint', None, None),
            ('hostport', None, None),
            ('state', None, _fmt_state),
        ]

        format_item = make_dict_to_table(schema)
        format_list = make_list_to_table(schema, header=False)

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)


class PartitionPrettyFormatter:
    """Pretty table partition formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""

        limits_tbl = make_list_to_table([
            ('trait', None, None),
            ('cpu', None, None),
            ('disk', None, None),
            ('memory', None, None),
        ])

        list_schema = [
            ('id', 'partition', None),
            ('cell', None, None),
            ('cpu', None, None),
            ('disk', None, None),
            ('memory', None, None),
            ('limits', None, limits_tbl),
            ('system', 'systems', None),
            ('down threshold', 'down-threshold', None),
            ('reboot schedule', 'reboot-schedule', None),
        ]
        item_schema = list_schema + [
            ('data', None, yaml.dump)
        ]

        format_item = make_dict_to_table(item_schema)
        format_list = make_list_to_table(list_schema)

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)


class CronPrettyFormatter:
    """Pretty table formatter for cron jobs."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        schema = [
            ('id', '_id', None),
            ('resource', None, None),
            ('event', None, None),
            ('action', None, None),
            ('count', None, None),
            ('expression', None, None),
            ('next_run_time', None, None),
            ('timezone', None, None),
        ]

        format_item = make_dict_to_table(schema)
        format_list = make_list_to_table(schema)

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)


class AppDNSPrettyFormatter:
    """Pretty table App Groups formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        schema = [('name', '_id', None),
                  ('scope', None, None),
                  ('cells', None, None),
                  ('pattern', None, None),
                  ('endpoints', None, None),
                  ('alias', None, None)]

        format_item = make_dict_to_table(schema)
        format_list = make_list_to_table(schema)

        if isinstance(item, list):
            return format_list(item)

        return format_item(item)
