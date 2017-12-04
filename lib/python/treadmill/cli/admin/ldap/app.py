"""Implementation of treadmill admin ldap CLI app_group plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io

import click
from ldap3.core import exceptions as ldap_exceptions

from treadmill import admin
from treadmill import cli
from treadmill import context
from treadmill import yamlwrapper as yaml


def init():
    """Configures app CLI group"""
    # Disable too many branches.
    #
    # pylint: disable=R0912
    formatter = cli.make_formatter('app')

    @click.group()
    def app():
        """Manage applications"""
        pass

    @app.command()
    @click.option('-m', '--manifest', help='Application manifest.',
                  type=click.Path(exists=True, readable=True))
    @click.argument('app')
    @cli.admin.ON_EXCEPTIONS
    def configure(app, manifest):
        """Create, get or modify an app configuration"""
        admin_app = admin.Application(context.GLOBAL.ldap.conn)
        if manifest:
            with io.open(manifest, 'rb') as fd:
                data = yaml.load(stream=fd)
            try:
                admin_app.create(app, data)
            except ldap_exceptions.LDAPEntryAlreadyExistsResult:
                admin_app.replace(app, data)

        try:
            cli.out(formatter(admin_app.get(app)))
        except ldap_exceptions.LDAPNoSuchObjectResult:
            click.echo('App does not exist: %s' % app, err=True)

    @app.command(name='list')
    @cli.admin.ON_EXCEPTIONS
    def _list():
        """List configured applicaitons"""
        admin_app = admin.Application(context.GLOBAL.ldap.conn)
        cli.out(formatter(admin_app.list({})))

    @app.command()
    @click.argument('app')
    @cli.admin.ON_EXCEPTIONS
    def delete(app):
        """Delete applicaiton"""
        admin_app = admin.Application(context.GLOBAL.ldap.conn)
        try:
            admin_app.delete(app)
        except ldap_exceptions.LDAPNoSuchObjectResult:
            click.echo('App does not exist: %s' % app, err=True)

    del delete
    del _list
    del configure

    return app
