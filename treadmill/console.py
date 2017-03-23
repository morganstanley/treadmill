"""Treadmill console entry point."""


import logging
import logging.config
import os
import tempfile
import traceback

import click
import requests
import yaml

# pylint complains about imports from treadmill not grouped, but import
# dependencies need to come first.
#
# pylint: disable=C0412
import treadmill
from treadmill import cli


# pylint complains "No value passed for parameter 'ldap' in function call".
# This is ok, as these parameters come from click decorators.
#
# pylint: disable=E1120
#
# TODO: add options to configure logging.
@click.group(cls=cli.make_multi_command('treadmill.cli'))
@click.option('--dns-domain', required=False,
              envvar='TREADMILL_DNS_DOMAIN',
              callback=cli.handle_context_opt,
              is_eager=True,
              expose_value=False)
@click.option('--ldap', required=False, envvar='TREADMILL_LDAP',
              type=cli.LIST,
              callback=cli.handle_context_opt,
              is_eager=True,
              expose_value=False)
@click.option('--ldap-search-base', required=False,
              envvar='TREADMILL_LDAP_SEARCH_BASE',
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

    # Default logging to cli.yml, at CRITICAL, unless --debug
    cli_log_conf_file = os.path.join(treadmill.TREADMILL, 'etc', 'logging',
                                     'cli.yml')
    try:
        with open(cli_log_conf_file, 'r') as fh:
            log_config = yaml.load(fh)
            logging.config.dictConfig(log_config)
    except IOError:
        with tempfile.NamedTemporaryFile(delete=False, mode='w') as f:
            traceback.print_exc(file=f)
            click.echo('Unable to load log conf: %s [ %s ]' %
                       (cli_log_conf_file, f.name), err=True)
        return

    if debug:
        ctx.obj['logging.debug'] = True
        logging.getLogger('treadmill').setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
