import os.path, pkgutil
import treadmill.cli
import click.testing
from click.core import Group
import importlib

failures = []

def _print_cli_info(runner, cli_pkg, mods, path):
    for mod in mods:
        try:
            cli = importlib.import_module(path + '.' + mod).init()
            _output = runner.invoke(cli, ['--help']).output
            print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
            print("Module: " + path + '.' + mod)
            print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
            print("::\n")
            click.echo("\t\t" + "\t\t".join(_output.splitlines(True)))
        except:
            failures.append(path + '.' + mod)
        if type(cli) is Group:
            subcommands = sorted(cli.list_commands(None))
            click.echo("\n")
        else:
            subcommands = []

        for _subcommand in subcommands:
            _output = runner.invoke(cli, [_subcommand, '--help']).output
            if 'Error: Missing option' not in  _output:
                click.echo("\t\t" + "\t\t".join(_output.splitlines(True)))

        submods = sorted([name for _, name, _ in pkgutil.iter_modules([cli_pkg + '/' + mod])])
        if submods:
            _print_cli_info(runner, cli_pkg + '/' + mod, submods, path + '.' + mod)

cli_pkg = os.path.dirname(treadmill.cli.__file__)
cli_mods = sorted([name for _, name, _ in pkgutil.iter_modules([cli_pkg])])
runner = click.testing.CliRunner()
click.echo(".. AUTO-GENERATED FILE - DO NOT EDIT!! Use `make cli_docs`.")
print("""
==============================================================
CLI
==============================================================
""")
_print_cli_info(runner, cli_pkg, cli_mods, 'treadmill.cli')

