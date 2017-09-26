"""Interpolate template files.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os

import click
import jinja2

from treadmill import cli
from treadmill import yamlwrapper as yaml


def init():
    """Return top level command handler."""

    @click.command()
    @click.argument('inputfile', type=click.Path(exists=True))
    @click.argument('params', nargs=-1,
                    type=click.Path(exists=True, readable=True))
    def interpolate(inputfile, params):
        """Interpolate input file template."""
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(os.path.dirname(inputfile)),
            keep_trailing_newline=True
        )

        data = {}
        for param in params:
            with io.open(param, 'rb') as fd:
                data.update(yaml.load(stream=fd))

        cli.out(env.get_template(os.path.basename(inputfile)).render(data))

    return interpolate
