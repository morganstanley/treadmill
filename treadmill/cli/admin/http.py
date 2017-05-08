"""Implementation of treadmill-admin CLI plugin."""


import click
import yaml

from treadmill import cli
from treadmill import restclient


def init():
    """Return top level command handler."""

    ctx = {}

    @click.group()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--api', required=False, help='API url to use.',
                  envvar='TREADMILL_RESTAPI')
    @click.option('--outfmt', type=click.Choice(['json', 'yaml']),
                  default='json')
    def top(api, outfmt):
        """Invoke Treadmill HTTP REST API."""
        cli.OUTPUT_FORMAT = outfmt
        ctx['api'] = [api]

    @top.command()
    @click.argument('path')
    @cli.ON_REST_EXCEPTIONS
    def get(path):
        """REST GET request."""
        response = restclient.get(ctx['api'], path)

        formatter = cli.make_formatter(None)
        cli.out(formatter(response.json()))

    @top.command()
    @click.argument('path')
    @click.argument('payload', type=click.File('rb'))
    @cli.ON_REST_EXCEPTIONS
    def post(path, payload):
        """REST POST request."""
        request = yaml.load(payload.read())
        response = restclient.post(ctx['api'], path, payload=request)

        formatter = cli.make_formatter(None)
        cli.out(formatter(response.json()))

    @top.command()
    @click.argument('path')
    @click.argument('payload', type=click.File('rb'))
    @cli.ON_REST_EXCEPTIONS
    def put(path, payload):
        """REST PUT request."""
        request = yaml.load(payload.read())
        response = restclient.put(ctx['api'], path, payload=request)

        formatter = cli.make_formatter(None)
        cli.out(formatter(response.json()))

    @top.command()
    @click.argument('path')
    @cli.ON_REST_EXCEPTIONS
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
