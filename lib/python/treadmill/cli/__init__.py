"""Treadmill commaand line helpers."""

# Disable too many lines in module warning.
#
# pylint: disable=C0302

from __future__ import absolute_import

import copy
import importlib
import os
import functools
import pkgutil
import re
import sys
import tempfile
import traceback
import logging

import pkg_resources
import click
from six.moves import configparser

import treadmill

from treadmill import context
from treadmill import plugin_manager


__path__ = pkgutil.extend_path(__path__, __name__)

EXIT_CODE_DEFAULT = 1


def init_logger(name):
    """Initialize logger."""
    log_conf_file = pkg_resources.resource_stream('treadmill',
                                                  '/logging/%s' % name)
    try:
        logging.config.fileConfig(log_conf_file)
    except configparser.Error:
        with tempfile.NamedTemporaryFile(delete=False) as f:
            traceback.print_exc(file=f)
            click.echo('Error parsing log conf: %s' %
                       log_conf_file, err=True)


def make_multi_command(module_name, **click_args):
    """Make a Click multicommand from all submodules of the module."""

    class MCommand(click.MultiCommand):
        """Treadmill CLI driver."""

        def __init__(self, *args, **kwargs):
            if kwargs and click_args:
                kwargs.update(click_args)

            click.MultiCommand.__init__(self, *args, **kwargs)

        def list_commands(self, ctx):
            climod = importlib.import_module(module_name)
            commands = set(
                [modulename for _loader, modulename, _ispkg
                 in pkgutil.iter_modules(climod.__path__)]
            )
            return sorted([cmd.replace('_', '-') for cmd in commands])

        def get_command(self, ctx, name):
            try:
                full_name = '.'.join([module_name, name.replace('-', '_')])
                mod = importlib.import_module(full_name)
                return mod.init()
            except Exception:  # pylint: disable=W0703
                with tempfile.NamedTemporaryFile(delete=False) as f:
                    traceback.print_exc(file=f)
                    click.echo(
                        'Unable to load plugin: %s [ %s ]' % (name, f.name),
                        err=True)
                return

    return MCommand


def make_commands(section, **click_args):
    """Make a Click multicommand from all submodules of the module."""

    class MCommand(click.MultiCommand):
        """Treadmill CLI driver."""

        def __init__(self, *args, **kwargs):
            if kwargs and click_args:
                kwargs.update(click_args)

            click.MultiCommand.__init__(self, *args, **kwargs)

        def list_commands(self, ctx):
            """Return list of commands in section."""
            return sorted(plugin_manager.names(section))

        def get_command(self, ctx, name):
            try:
                return plugin_manager.load(section, name).init()
            except KeyError:
                raise click.UsageError('Invalid command: %s' % name)

    return MCommand


def _read_password(value):
    """Heuristic to either read the password from file or return the value."""
    if os.path.exists(value):
        with open(value) as f:
            return f.read().strip()
    else:
        return value


def handle_context_opt(ctx, param, value):
    """Handle eager CLI options to configure context.

    The eager options are evaluated directly during parsing phase, and can
    affect other options parsing (like required/not).

    The only side effect of consuming these options are setting attributes
    of the global context.
    """

    def parse_dns_server(dns_server):
        """Parse dns server string"""
        if ':' in dns_server:
            hosts_port = dns_server.split(':')
            return (hosts_port[0].split(','), int(hosts_port[1]))
        else:
            return (dns_server.split(','), None)

    if not value or ctx.resilient_parsing:
        return None

    if value == '-':
        return None

    opt = param.name
    if opt == 'cell':
        context.GLOBAL.cell = value
    elif opt == 'dns_domain':
        context.GLOBAL.dns_domain = value
    elif opt == 'dns_server':
        context.GLOBAL.dns_server = parse_dns_server(value)
    elif opt == 'ldap':
        context.GLOBAL.ldap.url = value
    elif opt == 'ldap_suffix':
        context.GLOBAL.ldap_suffix = value
    elif opt == 'ldap_user':
        context.GLOBAL.ldap.user = value
    elif opt == 'ldap_pwd':
        context.GLOBAL.ldap.password = _read_password(value)
    elif opt == 'zookeeper':
        context.GLOBAL.zk.url = value
    elif opt == 'profile':
        context.GLOBAL.set_profile(value)
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

        items = re.split(r'(\w+=)', value)
        items.pop(0)

        keys = [key.rstrip('=') for key in items[0::2]]
        values = [value.rstrip(',') for value in items[1::2]]

        return dict(zip(keys, values))


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


def combine(list_of_values, sep=','):
    """Split and sum list of sep string into one list.
    """
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

    click.echo(string)


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

                with tempfile.NamedTemporaryFile(delete=False) as f:
                    traceback.print_exc(file=f)
                    click.echo('Error: %s [ %s ]' % (unhandled, f.name),
                               err=True)

                sys.exit(EXIT_CODE_DEFAULT)

        return _handle_any

    return wrap


OUTPUT_FORMAT = None


def make_formatter(pretty_formatter):
    """Makes a formatter."""

    def _format(item, how=None):
        """Formats the object given global format setting."""
        if OUTPUT_FORMAT is None:
            how = pretty_formatter
        else:
            how = OUTPUT_FORMAT

        try:
            fmt = plugin_manager.load('treadmill.formatters', how)
            return fmt.format(item)
        except KeyError:
            return str(item)

    return _format


def bad_exit(string, *args):
    """System exit non-zero with a string to sys.stderr.

    The printing takes care of the newline"""
    if args:
        string = string % args

    click.echo(string, err=True)
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
