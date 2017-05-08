"""Distributed supervision suite."""


import pkgutil
import click
import kazoo
import kazoo.exceptions  # noqa: F401
import ldap3  # noqa: F401

from treadmill import restclient  # noqa: F401
from treadmill import cli
from treadmill import context  # noqa: F401


__path__ = pkgutil.extend_path(__path__, __name__)


def init():
    """Return top level command handler."""

    @click.group(cls=cli.make_multi_command(__name__))
    def run():
        """Cross-cell supervision tools."""
        cli.init_logger('daemon.yml')

    return run
