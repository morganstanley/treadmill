"""Kerberos related CLI tools.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import pkgutil
import tempfile
import traceback

import pkgutil
import click

import dns.exception  # noqa: F401
import kazoo
import kazoo.exceptions  # noqa: F401
import ldap3  # noqa: F401

from treadmill import restclient  # noqa: F401
from treadmill import cli
from treadmill import context
from treadmill import yamlwrapper as yaml


__path__ = pkgutil.extend_path(__path__, __name__)


def init():
    """Return top level command handler."""

    @click.group(cls=cli.make_commands(__name__))
    @click.pass_context
    def run(_ctxp):
        """Manage Kerberos tickets."""

    return run
