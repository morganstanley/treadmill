import os.path, pkgutil
import treadmill.cli
import click.testing
from click.core import Group
import importlib

def _print_cli_info(runner, cli_pkg, mods, path):
    for mod in mods:
        print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
        print("Module: " + path + '.' + mod)
        print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
        print("::\n")

        cli = importlib.import_module(path + '.' + mod).init()
        click.echo("\t\t" + "\t\t".join(runner.invoke(cli, ['--help']).output.splitlines(True)))

        if type(cli) is Group:
            subcommands = sorted(cli.list_commands(None))
            click.echo("\n")
        else:
            subcommands = []

        for _subcommand in subcommands:
            click.echo("\t\t" + "\t\t".join(runner.invoke(cli, [_subcommand, '--help']).output.splitlines(True)))

        submods = sorted([name for _, name, _ in pkgutil.iter_modules([cli_pkg + '/' + mod])])
        if submods:
            _print_cli_info(runner, cli_pkg + '/' + mod, submods, path + '.' + mod)

cli_pkg = os.path.dirname(treadmill.cli.__file__)
cli_mods = sorted([name for _, name, _ in pkgutil.iter_modules([cli_pkg])])
runner = click.testing.CliRunner()
print("""
==============================================================
Treadmill-OSS CLI Cheatsheet
==============================================================
""")
_print_cli_info(runner, cli_pkg, cli_mods, 'treadmill.cli')
