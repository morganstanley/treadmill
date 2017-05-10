"""Interpolate template files.
"""

import os

import click
import yaml
import jinja2


def init():
    """Return top level command handler."""

    @click.command()
    @click.argument('inputfile', type=click.Path(exists=True))
    @click.argument('params', nargs=-1, type=click.File('rb'))
    def interpolate(inputfile, params):
        """Interpolate input file template."""
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(os.path.dirname(inputfile)),
            keep_trailing_newline=True
        )

        data = {}
        for param in params:
            data.update(yaml.load(param.read()))

        click.echo(
            env.get_template(
                os.path.basename(inputfile)
            ).render(data)
        )

    return interpolate
