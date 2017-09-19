import click

from treadmill import cli
from treadmill import restclient


def init():
    """Cloud CLI module"""

    @click.group()
    def cloud():
        """Manage Treadmill on cloud"""
        pass

    @cloud.group(name='ipa')
    @click.option('--api',
                  required=True,
                  help='API url to use.',
                  envvar='TREADMILL_IPA_RESTAPI')
    @click.pass_context
    def ipa_grp(ctx, api):
        """Create & Delete IPA Users, Hosts and Services"""
        if api:
            ctx.obj['api'] = api

    @ipa_grp.group(name='user')
    def user_grp():
        """Create and Delete IPA Users"""
        pass

    @user_grp.command('create')
    @click.argument('username')
    @cli.ON_REST_EXCEPTIONS
    @click.pass_context
    def create_user(ctx, username):
        """Creates an IPA User"""
        cli.out(
            restclient.post(
                api=ctx.obj.get('api'),
                url='/user/' + username,
                headers={'Content-Type': 'application/json'}
            ).content
        )

    @user_grp.command('delete')
    @click.argument('username')
    @cli.ON_REST_EXCEPTIONS
    @click.pass_context
    def delete_user(ctx, username):
        """Deletes an IPA User"""
        response = restclient.delete(
            api=ctx.obj.get('api'),
            url='/user/' + username,
            headers={'Content-Type': 'application/json'}
        )
        cli.out(
            response.content
        )

    @ipa_grp.group(name='host')
    def host_grp():
        """Create and Delete IPA Hosts"""
        pass

    @host_grp.command('create')
    @click.argument('hostname')
    @cli.ON_REST_EXCEPTIONS
    @click.pass_context
    def create_host(ctx, hostname):
        """Creates an IPA Host"""
        cli.out(
            restclient.post(
                api=ctx.obj.get('api'),
                url='/host/' + hostname,
                headers={'Content-Type': 'application/json'}
            ).content
        )

    @host_grp.command('delete')
    @click.argument('hostname')
    @cli.ON_REST_EXCEPTIONS
    @click.pass_context
    def delete_host(ctx, hostname):
        """Deletes an IPA Host"""
        cli.out(
            restclient.delete(
                api=ctx.obj.get('api'),
                url='/host/' + hostname,
                headers={'Content-Type': 'application/json'}
            ).content
        )

    @ipa_grp.group(name='service')
    def service_grp():
        """Add and Delete IPA Service"""
        pass

    @service_grp.command('add')
    @click.argument('hostname')
    @click.argument('service')
    @click.argument('domain')
    @cli.ON_REST_EXCEPTIONS
    @click.pass_context
    def service_add(ctx, domain, service, hostname):
        """Adds an IPA Service"""
        cli.out(
            restclient.post(
                api=ctx.obj.get('api'),
                url='/service/' + service,
                payload={
                    'domain': domain,
                    'hostname': hostname
                },
                headers={'Content-Type': 'application/json'}
            ).content
        )

    return cloud
