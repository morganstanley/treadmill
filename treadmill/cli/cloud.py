import click
import logging

from treadmill.infra import constants
from treadmill.infra.utils import mutually_exclusive_option, cli_callbacks
from treadmill import cli, restclient

_LOGGER = logging.getLogger(__name__)
_OPTIONS_FILE = 'manifest'


def init():
    """Cloud CLI module"""

    @click.group()
    @click.option('--domain', required=True,
                  envvar='TREADMILL_DNS_DOMAIN',
                  callback=cli_callbacks.validate_domain,
                  help='Domain for hosted zone')
    @click.option('--api',
                  required=True,
                  help='API URL',
                  envvar='TREADMILL_CLOUD_RESTAPI')
    @click.pass_context
    def cloud(ctx, domain, api):
        """Manage Treadmill on cloud"""
        ctx.obj['DOMAIN'] = domain
        ctx.obj['API'] = api

    @cloud.group(name='ipa')
    def ipa_grp():
        """Create & Delete IPA Users, Hosts and Services"""

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
                api=ctx.obj.get('API'),
                url='/ipa/user/' + username,
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
            api=ctx.obj.get('API'),
            url='/ipa/user/' + username,
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
                api=ctx.obj.get('API'),
                url='/ipa/host/' + hostname,
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
                api=ctx.obj.get('API'),
                url='/ipa/host/' + hostname,
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
    @cli.ON_REST_EXCEPTIONS
    @click.pass_context
    def service_add(ctx, service, hostname):
        """Adds an IPA Service"""
        cli.out(
            restclient.post(
                api=ctx.obj.get('API'),
                url='/ipa/service/' + service,
                payload={
                    'domain': ctx.obj.get('DOMAIN'),
                    'hostname': hostname
                },
                headers={'Content-Type': 'application/json'}
            ).content
        )

    @cloud.group()
    def configure():
        """Configure Treadmill EC2 Objects"""
        pass

    @configure.command(name='ldap')
    @click.option('--vpc-name',
                  required=True,
                  help='VPC name')
    @click.option('--region', help='Region for the vpc')
    @click.option('--key', required=True, help='SSH Key Name')
    @click.option('--name', required=True, help='LDAP Instance Name')
    @click.option('--image', required=True,
                  help='Image to use for instances e.g. RHEL-7.4')
    @click.option('--instance-type',
                  default=constants.INSTANCE_TYPES['EC2']['micro'],
                  help='AWS ec2 instance type')
    @click.option('--tm-release',
                  callback=cli_callbacks.current_release_version,
                  help='Treadmill release to use')
    @click.option('--app-root', default='/var/tmp',
                  help='Treadmill app root')
    @click.option('--ldap-cidr-block', default='172.23.1.0/24',
                  help='CIDR block for LDAP')
    @click.option('--ldap-subnet-id', help='Subnet ID for LDAP')
    @click.option('--cell-subnet-id', help='Subnet ID of Cell',
                  required=True)
    @click.option('--ipa-admin-password',
                  callback=cli_callbacks.ipa_password_prompt,
                  envvar='TREADMILL_IPA_ADMIN_PASSWORD',
                  help='Password for IPA admin')
    @click.option('-m', '--' + _OPTIONS_FILE,
                  cls=mutually_exclusive_option.MutuallyExclusiveOption,
                  mutually_exclusive=['region',
                                      'vpc_name',
                                      'key',
                                      'name',
                                      'image',
                                      'instance_type',
                                      'tm_release',
                                      'app_root',
                                      'ldap_subnet_id',
                                      'cell_subnet_id',
                                      'ipa_admin_password'
                                      'ldap_cidr_block'],
                  help="Options YAML file. ")
    @cli.ON_REST_EXCEPTIONS
    @click.pass_context
    def configure_ldap(ctx, vpc_name, region, key, name, image,
                       instance_type, tm_release, app_root,
                       ldap_cidr_block, ldap_subnet_id, cell_subnet_id,
                       ipa_admin_password, manifest):
        """Configure Treadmill LDAP"""
        domain = ctx.obj['DOMAIN']
        _url = '/cloud/vpc/' + vpc_name + '/domain/' + domain \
               + '/ldap/' + name
        cli.out(
            restclient.post(
                api=ctx.obj.get('API'),
                url=_url,
                payload={
                    "role": "ldap",
                    "key": key,
                    "cell_subnet_id": cell_subnet_id,
                    "region": region,
                    "app_root": app_root,
                    "tm_release": tm_release,
                    "ldap_cidr_block": ldap_cidr_block,
                    "instance_type": instance_type,
                    "image": image,
                    "ldap_subnet_id": ldap_subnet_id,
                    "ipa_admin_password": ipa_admin_password
                },
                headers={'Content-Type': 'application/json'}
            ).content
        )

    @configure.command(name='cell')
    @click.option('--vpc-name',
                  required=True,
                  help='VPC Name')
    @click.option('--region', help='Region for the vpc')
    @click.option('--name', default='TreadmillMaster',
                  help='Treadmill master name')
    @click.option('--key', required=True, help='SSH Key Name')
    @click.option('--count', default='3', type=int,
                  help='Number of Treadmill masters to spin up')
    @click.option('--image', required=True,
                  help='Image to use for new instances e.g. RHEL-7.4')
    @click.option('--instance-type',
                  default=constants.INSTANCE_TYPES['EC2']['micro'],
                  help='AWS ec2 instance type')
    @click.option('--tm-release',
                  callback=cli_callbacks.current_release_version,
                  help='Treadmill release to use')
    @click.option('--app-root', default='/var/tmp', help='Treadmill app root')
    @click.option('--cell-cidr-block', default='172.23.0.0/24',
                  help='CIDR block for the cell')
    @click.option('--subnet-id', help='Subnet ID')
    @click.option('--ipa-admin-password',
                  callback=cli_callbacks.ipa_password_prompt,
                  envvar='TREADMILL_IPA_ADMIN_PASSWORD',
                  help='Password for IPA admin')
    @click.option('-m', '--' + _OPTIONS_FILE,
                  cls=mutually_exclusive_option.MutuallyExclusiveOption,
                  mutually_exclusive=['region',
                                      'vpc_name',
                                      'name',
                                      'key',
                                      'count',
                                      'image',
                                      'instance_type',
                                      'tm_release',
                                      'app_root',
                                      'cell_cidr_block'
                                      'subnet_id',
                                      'ipa_admin_password'],
                  help="Options YAML file. ")
    @cli.ON_REST_EXCEPTIONS
    @click.pass_context
    def configure_cell(ctx, vpc_name, region, name, key, count, image,
                       instance_type, tm_release, app_root,
                       cell_cidr_block, subnet_id,
                       ipa_admin_password, manifest):
        """Configure Treadmill Cell"""
        domain = ctx.obj['DOMAIN']
        _url = '/cloud/vpc/' + vpc_name + '/domain/' + domain + '/cell'
        cli.out(
            restclient.post(
                api=ctx.obj.get('API'),
                url=_url,
                payload={
                    "role": "cell",
                    "key": key,
                    "tm_release": tm_release,
                    "region": region,
                    "app_root": app_root,
                    "cell_cidr_block": cell_cidr_block,
                    "instance_type": instance_type,
                    "image": image,
                    "ipa_admin_password": ipa_admin_password,
                    "subnet_id": subnet_id
                },
                headers={'Content-Type': 'application/json'}
            ).content
        )

    @configure.command(name='node')
    @click.option('--vpc-name',
                  required=True, help='VPC Name')
    @click.option('--region', help='Region for the vpc')
    @click.option('--name', default='TreadmillNode',
                  help='Node name')
    @click.option('--key', required=True, help='SSH Key Name')
    @click.option('--image', required=True,
                  help='Image to use for new node instance e.g. RHEL-7.4')
    @click.option('--instance-type',
                  default=constants.INSTANCE_TYPES['EC2']['large'],
                  help='AWS ec2 instance type')
    @click.option('--tm-release',
                  callback=cli_callbacks.current_release_version,
                  help='Treadmill release to use')
    @click.option('--app-root', default='/var/tmp/treadmill-node',
                  help='Treadmill app root')
    @click.option('--subnet-id', required=True, help='Subnet ID')
    @click.option('--ipa-admin-password',
                  callback=cli_callbacks.ipa_password_prompt,
                  envvar='TREADMILL_IPA_ADMIN_PASSWORD',
                  help='Password for IPA admin')
    @click.option('--with-api', required=False, is_flag=True,
                  default=False, help='Provision node with Treadmill APIs')
    @click.option('-m', '--' + _OPTIONS_FILE,
                  cls=mutually_exclusive_option.MutuallyExclusiveOption,
                  mutually_exclusive=['region',
                                      'vpc_name',
                                      'name',
                                      'key',
                                      'image',
                                      'instance_type',
                                      'tm_release',
                                      'app_root',
                                      'subnet_id',
                                      'ipa_admin_password'
                                      'with_api'],
                  help="Options YAML file. ")
    @cli.ON_REST_EXCEPTIONS
    @click.pass_context
    def configure_node(ctx, vpc_name, region, name, key, image,
                       instance_type, tm_release, app_root,
                       subnet_id, ipa_admin_password, with_api, manifest):
        """Configure new Node in Cell"""

        domain = ctx.obj['DOMAIN']
        _url = '/cloud/vpc/' + vpc_name + '/domain/' + domain \
               + '/server/' + name
        cli.out(
            restclient.post(
                api=ctx.obj.get('API'),
                url=_url,
                payload={
                    "role": "node",
                    "key": key,
                    "tm_release": tm_release,
                    "region": region,
                    "app_root": app_root,
                    "with_api": with_api,
                    "instance_type": instance_type,
                    "image": image,
                    "ipa_admin_password": ipa_admin_password,
                    "subnet_id": subnet_id
                },
                headers={'Content-Type': 'application/json'}
            ).content
        )

    @cloud.group()
    def delete():
        """Delete Treadmill EC2 Objects"""
        pass

    @delete.command(name='ldap')
    @click.option('--vpc-name',
                  required=True, help='VPC Name')
    @click.option('--name', help='LDAP Name',
                  required=True,
                  default="TreadmillLDAP")
    @click.pass_context
    def delete_ldap(ctx, vpc_name, name):
        """Delete LDAP"""
        domain = ctx.obj['DOMAIN']

        _url = '/cloud/vpc/' + vpc_name + '/domain/' + domain \
               + '/ldap/' + name
        cli.out(
            restclient.post(
                api=ctx.obj.get('API'),
                url=_url,
            ).content
        )

    @delete.command(name='cell')
    @click.option('--vpc-name',
                  required=True, help='VPC Name')
    @click.option('--subnet-id', help='Cell(Subnet) ID',
                  required=True)
    @click.pass_context
    def delete_cell(ctx, vpc_name, subnet_id):
        """Delete Cell"""
        domain = ctx.obj['DOMAIN']

        _url = '/cloud/vpc/' + vpc_name + '/domain/' + domain \
               + '/cell/' + subnet_id
        cli.out(
            restclient.post(
                api=ctx.obj.get('API'),
                url=_url,
            ).content
        )

    @delete.command(name='node')
    @click.option('--vpc-name',
                  required=True, help='VPC Name')
    @click.option('--name', help='Node Name',
                  required=True)
    @click.pass_context
    def delete_node(ctx, vpc_name, name):
        """Delete Node"""
        domain = ctx.obj['DOMAIN']

        _url = '/cloud/vpc/' + vpc_name + '/domain/' + domain \
               + '/server/' + name
        cli.out(
            restclient.post(
                api=ctx.obj.get('API'),
                url=_url,
            ).content
        )

    @cloud.group('list')
    def _list():
        """Show Treadmill Cloud Resources"""
        pass

    @_list.command(name='vpc')
    @click.option('--vpc-name',
                  help='VPC Name')
    @click.pass_context
    def vpc_resources(ctx, vpc_name):
        """Show VPC(s)"""
        domain = ctx.obj['DOMAIN']
        _url = '/cloud/vpc?domain=' + domain
        if vpc_name:
            _url += '&vpc_name=' + vpc_name
        cli.out(
            restclient.get(
                api=ctx.obj.get('API'),
                url=_url,
            ).content
        )

    @_list.command(name='cell')
    @click.option('--vpc-name',
                  required=True,
                  help='VPC Name')
    @click.option('--cell-id',
                  required=False,
                  help='Cell(Subnet) ID')
    @click.pass_context
    def cell_resources(ctx, vpc_name, cell_id):
        """Show Cell(s)"""
        domain = ctx.obj['DOMAIN']
        _url = '/cloud/vpc/' + vpc_name + '/domain/' + domain + '/cell'
        if cell_id:
            _url += '?cell_id=' + cell_id
        cli.out(
            restclient.get(
                api=ctx.obj.get('API'),
                url=_url,
            ).content
        )

    return cloud
