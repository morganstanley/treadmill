"""Entry point for treadmill manage ecosystem.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import pkgutil

import pkg_resources
import click

from treadmill import cli

__path__ = pkgutil.extend_path(__path__, __name__)


def make_manage_multi_command(module_name, **click_args):
    """Make a Click multicommand from all submodules of the module."""

    old_multi = cli.make_multi_command(module_name, **click_args)
    new_multi = cli.make_commands(module_name, **click_args)

    class MCommand(click.MultiCommand):
        """Treadmill CLI driver."""

        def __init__(self, *args, **kwargs):
            self.old_multi = old_multi(*args, **kwargs)
            self.new_multi = new_multi(*args, **kwargs)
            if kwargs and click_args:
                kwargs.update(click_args)

            click.MultiCommand.__init__(self, *args, **kwargs)

        def list_commands(self, ctx):
            old_commands = set(self.old_multi.list_commands(ctx))
            new_commands = set(self.new_multi.list_commands(ctx))
            return sorted(old_commands | new_commands)

        def get_command(self, ctx, name):
            try:
                return self.new_multi.get_command(ctx, name)
            except click.UsageError:
                pass
            return self.old_multi.get_command(ctx, name)

        def format_commands(self, ctx, formatter):
            rows = []
            for subcommand in self.list_commands(ctx):
                entry_points = list(pkg_resources.iter_entry_points(
                    module_name, subcommand))
                # Try get the help with importlib if entry_point not found
                if len(entry_points) == 0:
                    cmd = self.old_multi.get_command(ctx, subcommand)
                    if cmd is None:
                        continue
                    rows.append((subcommand, cmd.short_help or ''))
                else:
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
        """Manage applications."""
        pass

    return manage
