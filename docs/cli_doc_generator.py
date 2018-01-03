import importlib
import os
import pkgutil

import click.testing
from click import core

import treadmill.cli

os.environ.update({
    'TREADMILL_DNS_DOMAIN': 'treadmill.org',
    'TREADMILL_CLOUD_RESTAPI': 'http://example.com'
})

failures = []

def loop_commands(cli, commands):
    for _command in commands:
        click_echo(output(cli, _command))

def output(cli, *_commands):
    _commands = list(_commands) + ['--help']
    result = runner.invoke(cli, _commands, obj={})
    if result.exit_code == 0:
        return result.output
    else:
        failures.append([cli.name, _commands])
        return None

def click_echo(_output):
    if _output:
        click.echo("\t\t" + "\t\t".join(_output.splitlines(True)))

def loop_groups(cli):
    if type(cli) is core.Group:
        _commands = cli.commands
        click.echo("\n")
        _command_names = sorted(_commands.keys())
        loop_commands(cli, _command_names)
        for _command in _command_names:
            loop_groups(_commands.get(_command))

def loop_modules(runner, cli_pkg, mods, path):
    for mod in mods:
        try:
            cli = importlib.import_module(path + '.' + mod).init()
            print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
            print("Module: " + path + '.' + mod)
            print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
            print("::\n")
            click_echo(output(cli))
        except:
            failures.append(path + '.' + mod)

        loop_groups(cli)

        submods = sorted([name for _, name, _ in pkgutil.iter_modules([cli_pkg + '/' + mod])])
        if submods:
            loop_modules(runner, cli_pkg + '/' + mod, submods, path + '.' + mod)

cli_pkg = os.path.dirname(treadmill.cli.__file__)
cli_mods = sorted([name for _, name, _ in pkgutil.iter_modules([cli_pkg])])
runner = click.testing.CliRunner()

click.echo(
    """.. AUTO-GENERATED FILE - DO NOT EDIT!! Use `make cli_docs`.
==============================================================
CLI
==============================================================
"""
)
loop_modules(runner, cli_pkg, cli_mods, 'treadmill.cli')
