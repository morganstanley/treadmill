"""Manage core level cgroups.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import click

from treadmill import cgroups
from treadmill import cgutils
from treadmill import utils

_LOGGER = logging.getLogger(__name__)


def init():
    """Return top level command handler."""
    # Disable too many branches warning.
    #
    # pylint: disable=R0912

    @click.group(chain=True)
    def top():
        """Manage core cgroups."""

    @top.command(name='exec')
    @click.option('--into', multiple=True)
    @click.argument('subcommand', nargs=-1)
    def cgexec(into, subcommand):
        """execs command into given cgroup(s).
        """
        cgrps = [cgrp.split(':') for cgrp in into]

        for (subsystem, path) in cgrps:
            pathplus = path.split('=')
            if len(pathplus) == 2:
                group = os.path.dirname(pathplus[0])
                pseudofile = os.path.basename(pathplus[0])
                value = pathplus[1]
                cgroups.set_value(subsystem, group, pseudofile, value)
            else:
                cgutils.create(subsystem, path)
                cgroups.join(subsystem, path)

        if subcommand:
            execargs = list(subcommand)
            utils.sane_execvp(execargs[0], execargs)

    del cgexec

    return top
