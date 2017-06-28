"""Distributed supervision suite."""
from __future__ import absolute_import

import logging
import os
import pkgutil
import tempfile
import traceback
import yaml

import click
import kazoo
import kazoo.exceptions
import ldap3

import treadmill
from treadmill import restclient
from treadmill import cli
from treadmill import context


__path__ = pkgutil.extend_path(__path__, __name__)


def init():
    """Return top level command handler."""

    @click.group(cls=cli.make_commands(__name__))
    def run():
        """Cross-cell supervision tools."""
        cli.init_logger('daemon.conf')

    return run
