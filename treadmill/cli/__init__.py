"""Treadmill commaand line helpers."""


import copy
import json
import importlib
import os
import functools
import pkgutil
import re
import sys
import tempfile
import traceback
import logging

import click
import yaml
import prettytable

import treadmill

from treadmill import context
from treadmill import utils
from treadmill import restclient
import collections


__path__ = pkgutil.extend_path(__path__, __name__)

EXIT_CODE_DEFAULT = 1


def init_logger(name):
    """Initialize logger."""
    log_conf_file = os.path.join(treadmill.TREADMILL, 'etc', 'logging', name)
    try:
        with open(log_conf_file, 'r') as fh:
            log_config = yaml.load(fh)
            logging.config.dictConfig(log_config)

    except IOError:
        with tempfile.NamedTemporaryFile(delete=False, mode='w') as f:
            traceback.print_exc(file=f)
            click.echo('Unable to load log conf: %s [ %s ]' %
                       (log_conf_file, f.name), err=True)


def make_multi_command(module_name):
    """Make a Click multicommand from all submodules of the module."""

    class MCommand(click.MultiCommand):
        """Treadmill CLI driver."""

        def list_commands(self, ctx):
            climod = importlib.import_module(module_name)
            commands = set()
            for path in climod.__path__:
                for filename in os.listdir(path):
                    if filename in ['__init__.py', '__pycache__']:
                        continue

                    if filename.endswith('.py'):
                        commands.add(filename[:-3])

                    if os.path.isdir(os.path.join(path, filename)):
                        commands.add(filename)

            return sorted([cmd.replace('_', '-') for cmd in commands])

        def get_command(self, ctx, name):
            try:
                full_name = '.'.join([module_name, name.replace('-', '_')])
                mod = importlib.import_module(full_name)
                return mod.init()
            except Exception:  # pylint: disable=W0703
                with tempfile.NamedTemporaryFile(delete=False, mode='w') as f:
                    traceback.print_exc(file=f)
                    click.echo(
                        'Unable to load plugin: %s [ %s ]' % (name, f.name),
                        err=True)
                return

    return MCommand


def handle_context_opt(ctx, param, value):
    """Handle eager CLI options to configure context.

    The eager options are evaluated directly during parsing phase, and can
    affect other options parsing (like required/not).

    The only side effect of consuming these options are setting attributes
    of the global context.
    """
    if not value or ctx.resilient_parsing:
        return

    opt = param.name
    if opt == 'cell':
        context.GLOBAL.cell = value
    elif opt == 'dns_domain':
        context.GLOBAL.dns_domain = value
    elif opt == 'ldap':
        context.GLOBAL.ldap.url = value
    elif opt == 'ldap_search_base':
        context.GLOBAL.ldap.search_base = value
    elif opt == 'zookeeper':
        context.GLOBAL.zk.url = value
    else:
        raise click.UsageError('Invalid option: %s' % param.name)

    return value


class _CommaSepList(click.ParamType):
    """Custom input type for comma separated values."""
    name = 'list'

    def convert(self, value, param, ctx):
        """Convert command line argument to list."""
        if value is None:
            return []

        try:
            return value.split(',')
        except AttributeError:
            self.fail('%s is not a comma separated list' % value, param, ctx)


LIST = _CommaSepList()


class _KeyValuePairs(click.ParamType):
    """Custom input type for key/value pairs."""
    name = 'key/value pairs'

    def convert(self, value, param, ctx):
        """Convert command line argument to list."""
        if value is None:
            return {}

        items = value.split(',')
        result = {}
        for item in items:
            if item.find('=') == -1:
                self.fail('"%s" not a key/value pair, X=Y expected.' % item)
            key, value = item.split('=')
            result[key] = value
        return result


DICT = _KeyValuePairs()


def validate_memory(_ctx, _param, value):
    """Validate memory string."""
    if value is None:
        return

    if not re.search(r'\d+[KkMmGg]$', value):
        raise click.BadParameter('Memory format: nnn[K|M|G].')
    return value


def validate_disk(_ctx, _param, value):
    """Validate disk string."""
    if value is None:
        return
    if not re.search(r'\d+[KkMmGg]$', value):
        raise click.BadParameter('Disk format: nnn[K|M|Gyy].')
    return value


def validate_cpu(_ctx, _param, value):
    """Validate cpu string."""
    if value is None:
        return
    if not re.search(r'\d+%$', value):
        raise click.BadParameter('CPU format: nnn%.')
    return value


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


def _make_table(columns, header=False):
    """Make a table object for output."""
    table = prettytable.PrettyTable(columns)
    for col in columns:
        table.align[col] = 'l'

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

    if isinstance(key, str):
        keys = [key]
    else:
        keys = key

    raw_value = None
    while keys:
        key = keys.pop(0)
        if key in item:
            raw_value = item[key]
            break

    if isinstance(fmt, collections.Callable):
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
                value = ','.join(map(str, raw_value))
            else:
                value = raw_value
    return value


def dict_to_table(item, schema):
    """Display object as table."""
    table = _make_table(['key', '', 'value'], header=False)
    for column, key, fmt in schema:
        value = _cell(item, column, key, fmt)
        table.add_row([column, ':', value])

    return table


def make_dict_to_table(schema):
    """Return dict to table function given schema."""
    return lambda item: dict_to_table(item, schema)


def list_to_table(items, schema, header=True):
    """Display  list of items as table."""
    columns = [column for column, _, _ in schema]
    table = _make_table(columns, header=header)
    for item in items:
        row = []
        for column, key, fmt in schema:
            row.append(_cell(item, column, key, fmt))
        table.add_row(row)

    return table


def make_list_to_table(schema, header=True):
    """Return list to table function given schema."""
    return lambda items: list_to_table(items, schema, header)


def combine(list_of_values, sep=','):
    """Split and sum list of sep string into one list."""
    combined = sum(
        [str(values).split(sep) for values in list(list_of_values)],
        []
    )

    if combined == ['-']:
        combined = None

    return combined


def out(string, *args):
    """Print to stdout."""
    if args:
        string = string % args

    print(string)


def handle_exceptions(exclist):
    """Decorator that will handle exceptions and output friendly messages."""

    def wrap(f):
        """Returns decorator that wraps/handles exceptions."""
        exclist_copy = copy.copy(exclist)

        @functools.wraps(f)
        def wrapped_f(*args, **kwargs):
            """Wrapped function."""
            if not exclist_copy:
                f(*args, **kwargs)
            else:
                exc, handler = exclist_copy.pop(0)

                try:
                    wrapped_f(*args, **kwargs)
                except exc as err:
                    if isinstance(handler, str):
                        click.echo(handler, err=True)
                    elif handler is None:
                        click.echo(str(err), err=True)
                    else:
                        click.echo(handler(err), err=True)

                    sys.exit(EXIT_CODE_DEFAULT)

        @functools.wraps(f)
        def _handle_any(*args, **kwargs):
            """Default exception handler."""
            try:
                return wrapped_f(*args, **kwargs)
            except Exception as unhandled:  # pylint: disable=W0703

                with tempfile.NamedTemporaryFile(delete=False, mode='w') as f:
                    traceback.print_exc(file=f)
                    click.echo('Error: %s [ %s ]' % (unhandled, f.name),
                               err=True)

                sys.exit(EXIT_CODE_DEFAULT)

        return _handle_any

    return wrap


OUTPUT_FORMAT = 'pretty'


def make_formatter(pretty_formatter):
    """Makes a formatter."""

    def _format(item, how=None):
        """Formats the object given global format setting."""
        if how is None:
            how = OUTPUT_FORMAT

        formatters = {
            'json': json.dumps,
            'yaml': utils.dump_yaml,
        }

        if pretty_formatter is not None:
            try:
                formatters['pretty'] = pretty_formatter.format
            except AttributeError:
                formatters['pretty'] = pretty_formatter

        if how in formatters:
            return formatters[how](item)
        else:
            return str(item)

    return _format


class AppPrettyFormatter(object):
    """Pretty table app formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""

        services_restart_tbl = make_dict_to_table([
            ('limit', None, None),
            ('interval', None, None),
        ])

        command_fmt = lambda cmd: wrap_words(cmd.split(), 40, ' ', '\n   ')
        services_tbl = make_list_to_table([
            ('name', None, None),
            ('restart', None, services_restart_tbl),
            ('command', None, command_fmt),
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

        schema = [
            ('name', '_id', None),
            ('memory', None, None),
            ('cpu', None, None),
            ('disk', None, None),
            ('tickets', None, None),
            ('features', None, None),
            ('identity-group', 'identity_group', None),
            ('shared-ip', 'shared_ip', None),
            ('services', None, services_tbl),
            ('endpoints', None, endpoints_tbl),
            ('environ', None, environ_tbl),
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


class AppMonitorPrettyFormatter(object):
    """Pretty table app monitor formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        schema = [('monitor', '_id', None),
                  ('count', 'count', None)]

        format_item = make_dict_to_table(schema)
        format_list = make_list_to_table(schema)

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)


class IdentityGroupPrettyFormatter(object):
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


class ServerPrettyFormatter(object):
    """Pretty table server formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""

        schema = [
            ('name', '_id', None),
            ('cell', None, None),
            ('traits', None, None),
            ('label', None, None),
        ]

        format_item = make_dict_to_table(schema)
        format_list = make_list_to_table(schema)

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)


class ServerNodePrettyFormatter(object):
    """Pretty table server (scheduler) node formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        schema = [('name', None, None),
                  ('memory', None, None),
                  ('cpu', None, None),
                  ('disk', None, None),
                  ('parent', None, None),
                  ('traits', None, None),
                  ('valid_until', None, None)]

        format_item = make_dict_to_table(schema)
        format_list = make_list_to_table(schema)

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)


class LdapSchemaPrettyFormatter(object):
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


class BucketPrettyFormatter(object):
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


class CellPrettyFormatter(object):
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

        schema = [
            ('name', '_id', None),
            ('version', None, None),
            ('root', None, None),
            ('username', None, None),
            ('location', None, None),
            ('archive-server', None, None),
            ('archive-username', None, None),
            ('ssq-namespace', None, None),
            ('masters', None, masters_tbl),
        ]

        format_item = make_dict_to_table(schema)

        format_list = make_list_to_table([
            ('name', '_id', None),
            ('version', None, None),
            ('username', None, None),
            ('root', None, None),
        ])

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)


class DNSPrettyFormatter(object):
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


class AppGroupPrettyFormatter(object):
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


class TenantPrettyFormatter(object):
    """Pretty table tenant formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        schema = [
            ('tenant', ['_id', 'tenant'], None),
            ('system', 'systems', None),
            ('allocations', 'allocations', AllocationPrettyFormatter.format),
        ]

        format_item = make_dict_to_table(schema)
        format_list = make_list_to_table(schema)

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)


class AllocationPrettyFormatter(object):
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
            ('label', None, None),
            ('rank', None, None),
            ('max-utilization', None, None),
            ('memory', None, None),
            ('cpu', None, None),
            ('disk', None, None),
            ('traits', None, '\n'.join),
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


class InstanceStatePrettyFormatter(object):
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


class EndpointPrettyFormatter(object):
    """Pretty table endpoint formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        schema = [
            ('name', None, None),
            ('proto', None, None),
            ('endpoint', None, None),
            ('hostport', None, None),
        ]

        format_item = make_dict_to_table(schema)
        format_list = make_list_to_table(schema, header=False)

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)


def bad_exit(string, *args):
    """System exit non-zero with a string to sys.stderr.

    The printing takes care of the newline"""
    if args:
        string = string % args

    click.echo(click.style(string, fg='red'), err=True)
    sys.exit(-1)


def echo_colour(colour, string, *args):
    """click.echo colour with support for placeholders, e.g. %s"""
    if args:
        string = string % args

    click.echo(click.style(string, fg=colour))


def echo_green(string, *args):
    """click.echo green with support for placeholders, e.g. %s"""
    echo_colour('green', string, *args)


def echo_yellow(string, *args):
    """click.echo yellow with support for placeholders, e.g. %s"""
    echo_colour('yellow', string, *args)


def echo_red(string, *args):
    """click.echo yellow with support for placeholders, e.g. %s"""
    echo_colour('red', string, *args)


def handle_not_authorized(err):
    """Handle REST NotAuthorizedExceptions"""
    msg = str(err)
    msgs = [re.sub(r'failure: ', '    ', line) for line in msg.split(r'\n')]
    echo_red('Not authorized.')
    click.echo('\n'.join(msgs), nl=False)


REST_EXCEPTIONS = [
    (restclient.NotFoundError, 'Resource not found'),
    (restclient.AlreadyExistsError, 'Resource already exists'),
    (restclient.ValidationError, None),
    (restclient.NotAuthorizedError, handle_not_authorized),
    (restclient.BadRequestError, None),
    (restclient.MaxRequestRetriesError, None)
]

ON_REST_EXCEPTIONS = handle_exceptions(REST_EXCEPTIONS)
