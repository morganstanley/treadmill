"""Kerberos related CLI tools."""


import pkgutil
import click

import dns.exception  # noqa: F401
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
    @click.pass_context
    def run(_ctxp):
        """Manage Kerberos tickets."""

    return run
