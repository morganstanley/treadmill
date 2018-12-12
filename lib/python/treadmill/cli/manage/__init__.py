"""Entry point for treadmill manage ecosystem.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import click
import pkg_resources

from treadmill import cli, plugin_manager, utils

_LOGGER = logging.getLogger(__name__)


def make_manage_multi_command(module_name, **click_args):
    """Make a Click multicommand from all submodules of the module."""

    commands = cli.make_commands(module_name, **click_args)

    class MCommand(click.MultiCommand):
        """Treadmill CLI driver."""

        def __init__(self, *args, **kwargs):
            self.commands = commands(*args, **kwargs)
            if kwargs and click_args:
                kwargs.update(click_args)

            click.MultiCommand.__init__(self, *args, **kwargs)

        def list_commands(self, ctx):
            return sorted(set(self.commands.list_commands(ctx)))

        def invoke(self, ctx):
            """
            invoke the command in a subprocess if it is executable
            otherwise use it in process
            """
            name = ctx.protected_args[0]
            try:
                module = plugin_manager.load(module_name, name)
            except KeyError:
                return super(MCommand, self).invoke(ctx)

            module_path = module.__file__
            if module_path.endswith('pyc'):
                module_path = module_path[:-1]
            # shebang doesn't work on windows
            # we use .cmd or a hardcoded default interpreter
            if os.name == 'nt':
                nt_path = module_path[:-2] + 'cmd'
                if os.path.exists(nt_path):
                    os.execvp(nt_path, [nt_path] + ctx.args)
                else:
                    _LOGGER.critical(
                        "%s cli is not supported on windows", name)
            else:
                is_exec = os.access(module_path, os.X_OK)
                if not is_exec:
                    return super(MCommand, self).invoke(ctx)
                utils.sane_execvp(module_path,
                                  [os.path.basename(module_path)] + ctx.args)
            return None

        def get_command(self, ctx, cmd_name):
            return self.commands.get_command(ctx, cmd_name)

        def format_commands(self, ctx, formatter):
            rows = []
            for subcommand in self.list_commands(ctx):
                entry_points = list(pkg_resources.iter_entry_points(
                    module_name, subcommand))
                # Try get the help with importlib if entry_point not found
                dist = entry_points[0].dist
                if dist.has_metadata('cli_help'):
                    help_text = dist.get_metadata('cli_help')
                else:
                    help_text = ''
                rows.append((subcommand, help_text))

            if rows:
                with formatter.section('Commands'):
                    formatter.write_dl(rows)

    return MCommand


def init():
    """Return top level command handler."""

    @click.group(cls=make_manage_multi_command('treadmill.cli.manage'))
    def manage():
        """Manage applications.
        """

    return manage
