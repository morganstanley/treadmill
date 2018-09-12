"""Implementation of treadmill-admin CLI plugin."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io

import click

from treadmill import cli
from treadmill import restclient
from treadmill import yamlwrapper as yaml


def init():
    """Return top level command handler."""

    ctx = {}

    @click.group()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    # TODO: it is not clear why this should TREADMIL_ADMINAPI, as this module
    #       can be used to invoke any API. Leaving it for now.
    @click.option('--api', required=False, help='API url to use.',
                  envvar='TREADMILL_ADMINAPI')
    @click.option('--outfmt', type=click.Choice(['json', 'yaml']),
                  default='json')
    def top(api, outfmt):
        """Invoke Treadmill HTTP REST API."""
        cli.OUTPUT_FORMAT = outfmt
        ctx['api'] = [api]

    @top.command()
    @click.argument('path')
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def get(path):
        """REST GET request."""
        response = restclient.get(ctx['api'], path)

        formatter = cli.make_formatter(None)
        cli.out(formatter(response.json()))

    @top.command()
    @click.argument('path')
    @click.argument('payload', type=click.Path(exists=True, readable=True))
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def post(path, payload):
        """REST POST request."""
        with io.open(payload, 'rb') as fd:
            request = yaml.load(stream=fd)
        response = restclient.post(ctx['api'], path, payload=request)

        formatter = cli.make_formatter(None)
        cli.out(formatter(response.json()))

    @top.command()
    @click.argument('path')
    @click.argument('payload', type=click.Path(exists=True, readable=True))
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def put(path, payload):
        """REST PUT request."""
        with io.open(payload, 'rb') as fd:
            request = yaml.load(stream=fd)
        response = restclient.put(ctx['api'], path, payload=request)

        formatter = cli.make_formatter(None)
        cli.out(formatter(response.json()))

    @top.command()
    @click.argument('path')
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def delete(path):
        """REST DELETE request."""
        response = restclient.delete(ctx['api'], path)

        formatter = cli.make_formatter(None)
        cli.out(formatter(response.json()))

    del get
    del post
    del put
    del delete

    return top
