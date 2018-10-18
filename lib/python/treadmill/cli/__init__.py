"""Treadmill commaand line helpers.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

# Disable too many lines in module warning.
#
# pylint: disable=C0302

import codecs
import copy
import functools
import io
import logging
import os
import pkgutil
import re
import sys
import traceback

import click

import six
from six.moves import configparser

import treadmill

from treadmill import restclientopts
from treadmill import plugin_manager
from treadmill import context
from treadmill import utils
from treadmill import subproc


EXIT_CODE_DEFAULT = 1

# Disable unicode_literals click warning.
click.disable_unicode_literals_warning = True


def init_logger(name):
    """Initialize logger.
    """
    try:
        # logging configuration files in json format
        conf = treadmill.logging.load_logging_conf(name)
        logging.config.dictConfig(conf)
    except configparser.Error:
        # TODO: Incidentally, tempfile adds 2M memory, and it is used only
        #       in case of exception. Need to move this elsewhere.
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, mode='w') as f:
            traceback.print_exc(file=f)
            click.echo('Error parsing log conf: {name}'.format(name=name),
                       err=True)


def init_profile():
    """Initailize profile.
    """
    if 'TREADMILL_ALIASES_PATH' in os.environ:
        subproc.load_aliases(os.environ['TREADMILL_ALIASES_PATH'])
    else:
        packages = ['aliases']
        profile = context.GLOBAL.get_profile_name()
        if profile:
            packages.append('aliases.{}'.format(profile))
        subproc.load_packages(packages)


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

        def get_command(self, ctx, cmd_name):
            """Return dymanically constructed command."""
            try:
                return plugin_manager.load(section, cmd_name).init()
            except ImportError as import_err:
                print(
                    'dependency error: {}:{} - {}'.format(
                        section, cmd_name, str(import_err)
                    ),
                    file=sys.stderr
                )
            except KeyError:
                raise click.UsageError('Invalid command: %s' % cmd_name)

    return MCommand


def _read_password(value):
    """Heuristic to either read the password from file or return the value."""
    if os.path.exists(value):
        with io.open(value) as f:
            return f.read().strip()
    else:
        return value


# pylint: disable=too-many-branches
def handle_context_opt(ctx, param, value):
    """Handle eager CLI options to configure context.

    The eager options are evaluated directly during parsing phase, and can
    affect other options parsing (like required/not).

    The only side effect of consuming these options are setting attributes
    of the global context.
    """
    # pylint: disable=too-many-branches

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
        cell_parts = value.split('.')
        context.GLOBAL.cell = cell_parts.pop(0)
        if cell_parts:
            context.GLOBAL.dns_domain = '.'.join(cell_parts)
    elif opt == 'dns_domain':
        context.GLOBAL.dns_domain = value
    elif opt == 'dns_server':
        context.GLOBAL.dns_server = parse_dns_server(value)
    elif opt == 'ldap':
        context.GLOBAL.ldap.url = value
    elif opt == 'ldap_master':
        context.GLOBAL.ldap.write_url = value
    elif opt == 'ldap_suffix':
        context.GLOBAL.ldap_suffix = value
    elif opt == 'ldap_user':
        context.GLOBAL.ldap.user = value
    elif opt == 'ldap_pwd':
        context.GLOBAL.ldap.password = _read_password(value)
    elif opt == 'zookeeper':
        context.GLOBAL.zk.url = value
    elif opt == 'profile':
        context.GLOBAL.set_profile_name(value)
        init_profile()
    elif opt == 'api_service_principal':
        restclientopts.AUTH_PRINCIPAL = value
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


class Enums(click.ParamType):
    """Custom input type for comma separated enums."""
    name = 'enumlist'

    def __init__(self, choices):
        self.choices = choices

    def get_metavar(self, param):
        return '[%s]' % '|'.join(self.choices)

    def get_missing_message(self, param):
        return 'Choose from %s.' % ', '.join(self.choices)

    def convert(self, value, param, ctx):
        """Convert command line argument to list."""
        if value is None:
            return []

        choices = []
        try:
            for val in value.split(','):
                if val in self.choices:
                    choices.append(val)
                else:
                    self.fail(
                        'invalid choice: %s. (choose from %s)' %
                        (val, ', '.join(self.choices)),
                        param, ctx
                    )
            return choices

        except AttributeError:
            self.fail('%s is not a comma separated list' % value, param, ctx)


class _KeyValuePairs(click.ParamType):
    """Custom input type for key/value pairs."""
    name = 'key/value pairs'

    def convert(self, value, param, ctx):
        """Convert command line argument to list."""
        if value is None:
            return {}

        items = re.split(r'([\w\.\-]+=)', value)
        items.pop(0)

        keys = [key.rstrip('=') for key in items[0::2]]
        values = [value.rstrip(',') for value in items[1::2]]

        return dict(zip(keys, values))


DICT = _KeyValuePairs()


def validate_memory(_ctx, _param, value):
    """Validate memory string."""
    if value is None:
        return None

    if not re.search(r'\d+[KkMmGg]$', value):
        raise click.BadParameter('Memory format: nnn[K|M|G].')
    return value


def validate_disk(_ctx, _param, value):
    """Validate disk string."""
    if value is None:
        return None
    if not re.search(r'\d+[KkMmGg]$', value):
        raise click.BadParameter('Disk format: nnn[K|M|G].')
    return value


def validate_cpu(_ctx, _param, value):
    """Validate cpu string."""
    if value is None:
        return None
    if not re.search(r'\d+%$', value):
        raise click.BadParameter('CPU format: nnn%.')
    return value


def validate_cpuset_cores(_ctx, _param, value):
    """Validate cpuset cores string."""
    if value is None:
        return None
    if not re.search(r'\d+\-?\d*(,\d+\-?\d*)*$', value):
        raise click.BadParameter('CPU cores format: nnn[,nnn-[nnn]].')
    return value


def validate_reboot_schedule(_ctx, _param, value):
    """Validate reboot schedule specification."""
    if value is None:
        return None
    try:
        utils.reboot_schedule(value)
    except ValueError:
        raise click.BadParameter('Invalid reboot schedule. (eg.: "sat,sun")')
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
                    if isinstance(handler, six.string_types):
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

            except click.UsageError as usage_err:
                click.echo('Usage error: %s' % str(usage_err), err=True)
                sys.exit(EXIT_CODE_DEFAULT)

            except Exception as unhandled:  # pylint: disable=W0703
                # TODO: see similar comment as to why lazy import tempfile.
                import tempfile

                with tempfile.NamedTemporaryFile(delete=False, mode='w') as f:
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
