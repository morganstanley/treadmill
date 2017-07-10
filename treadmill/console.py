"""Treadmill console entry point.
"""

import logging
import logging.config

import click
import requests

# pylint complains about imports from treadmill not grouped, but import
# dependencies need to come first.
#
# pylint: disable=C0412
from treadmill import cli


# pylint complains "No value passed for parameter 'ldap' in function call".
# This is ok, as these parameters come from click decorators.
#
# pylint: disable=E1120
#
# TODO: add options to configure logging.
@click.group(cls=cli.make_commands('treadmill.cli'))
@click.option('--dns-domain', required=False,
              envvar='TREADMILL_DNS_DOMAIN',
              callback=cli.handle_context_opt,
              is_eager=True,
              expose_value=False)
@click.option('--dns-server', required=False, envvar='TREADMILL_DNS_SERVER',
              callback=cli.handle_context_opt,
              is_eager=True,
              expose_value=False)
@click.option('--ldap', required=False, envvar='TREADMILL_LDAP',
              callback=cli.handle_context_opt,
              is_eager=True,
              expose_value=False)
@click.option('--ldap-user', required=False, envvar='TREADMILL_LDAP_USER',
              callback=cli.handle_context_opt,
              is_eager=True,
              expose_value=False)
@click.option('--ldap-pwd', required=False, envvar='TREADMILL_LDAP_PWD',
              callback=cli.handle_context_opt,
              is_eager=True,
              expose_value=False)
@click.option('--ldap-suffix', required=False,
              envvar='TREADMILL_LDAP_SUFFIX',
              callback=cli.handle_context_opt,
              is_eager=True,
              expose_value=False)
@click.option('--outfmt', type=click.Choice(['json', 'yaml']))
@click.option('--debug/--no-debug',
              help='Sets logging level to debug',
              is_flag=True, default=False)
@click.option('--with-proxy', required=False, is_flag=True,
              help='Enable proxy environment variables.',
              default=False)
@click.pass_context
def run(ctx, with_proxy, outfmt, debug):
    """Treadmill CLI."""
    ctx.obj = {}
    ctx.obj['logging.debug'] = False

    requests.Session().trust_env = with_proxy

    if outfmt:
        cli.OUTPUT_FORMAT = outfmt

    # Default logging to cli.conf, at CRITICAL, unless --debug
    cli.init_logger('cli.conf')
    if debug:
        ctx.obj['logging.debug'] = True
        logging.getLogger('treadmill').setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
