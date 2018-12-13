"""Implementation of treadmill admin ldap CLI app_group plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io

import click
from treadmill.admin import exc as admin_exceptions

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
        """Manage applications.
        """

    @app.command()
    @click.option('-m', '--manifest', help='Application manifest.',
                  type=click.Path(exists=True, readable=True))
    @click.argument('app')
    @cli.admin.ON_EXCEPTIONS
    def configure(app, manifest):
        """Create, get or modify an app configuration"""
        admin_app = context.GLOBAL.admin.application()
        if manifest:
            with io.open(manifest, 'rb') as fd:
                data = yaml.load(stream=fd)
            try:
                admin_app.create(app, data)
            except admin_exceptions.AlreadyExistsResult:
                admin_app.replace(app, data)

        try:
            cli.out(formatter(admin_app.get(app, dirty=True)))
        except admin_exceptions.NoSuchObjectResult:
            click.echo('App does not exist: %s' % app, err=True)

    @app.command(name='list')
    @cli.admin.ON_EXCEPTIONS
    def _list():
        """List configured applicaitons"""
        admin_app = context.GLOBAL.admin.application()
        cli.out(formatter(admin_app.list({})))

    @app.command()
    @click.argument('app')
    @cli.admin.ON_EXCEPTIONS
    def delete(app):
        """Delete applicaiton"""
        admin_app = context.GLOBAL.admin.application()
        try:
            admin_app.delete(app)
        except admin_exceptions.NoSuchObjectResult:
            click.echo('App does not exist: %s' % app, err=True)

    del delete
    del _list
    del configure

    return app
