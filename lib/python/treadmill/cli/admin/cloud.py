import os
import click
from pprint import pprint
import logging

from treadmill.infra import constants, connection, vpc, subnet
from treadmill.infra.setup import ipa, ldap, node, cell
from treadmill.infra.utils import mutually_exclusive_option, cli_callbacks
from treadmill.infra.utils import security_group
from treadmill import cli


_LOGGER = logging.getLogger(__name__)
_OPTIONS_FILE = 'manifest'


def init():
    """Cloud CLI module"""

    @click.group()
    @click.option('--domain', required=True,
                  envvar='TREADMILL_DNS_DOMAIN',
                  callback=cli_callbacks.validate_domain,
                  help='Domain for hosted zone')
    @click.pass_context
    def cloud(ctx, domain):
        """Manage Treadmill on cloud"""
        ctx.obj['DOMAIN'] = domain

    @cloud.group()
    @click.option('--proid', default='treadmld',
                  show_default=True,
                  help='Proid user for treadmill')
    @click.pass_context
    def configure(ctx, proid):
        """Configure Treadmill EC2 Objects"""
        ctx.obj['PROID'] = proid

    @configure.command(name='vpc')
    @click.option(
        '--name',
        required=True,
        help='VPC name',
        callback=cli_callbacks.validate_vpc_name
    )
    @click.option('--region', help='Region for the vpc')
    @click.option('--vpc-cidr-block', default='172.23.0.0/16',
                  show_default=True,
                  help='CIDR block for the vpc')
    @click.option('-m', '--' + _OPTIONS_FILE,
                  cls=mutually_exclusive_option.MutuallyExclusiveOption,
                  mutually_exclusive=['region',
                                      'vpc_cidr_block',
                                      'name'],
                  help="Options YAML file. ")
    @click.pass_context
    @cli.ON_CLI_EXCEPTIONS
    def configure_vpc(ctx, name, region, vpc_cidr_block,
                      manifest):
        """Configure Treadmill VPC"""
        domain = ctx.obj['DOMAIN']

        if region:
            connection.Connection.context.region_name = region

        connection.Connection.context.domain = domain

        _vpc = vpc.VPC.setup(
            name=name,
            cidr_block=vpc_cidr_block,
        )

        click.echo(
            pprint(_vpc.show())
        )

    @configure.command(name='ldap')
    @click.option('--vpc-name', 'vpc_id',
                  required=True,
                  callback=cli_callbacks.convert_to_vpc_id,
                  help='VPC name')
    @click.option('--key', required=True, help='SSH Key Name')
    @click.option('--name', required=True, help='LDAP Instance Name')
    @click.option('--image', required=True,
                  help='Image to use for instances e.g. RHEL-7.4')
    @click.option('--subnet-name', help='Subnet Name for LDAP',
                  required=True)
    @click.option('--region', help='Region for the vpc')
    @click.option('--instance-type',
                  default=constants.INSTANCE_TYPES['EC2']['micro'],
                  show_default=True,
                  help='AWS ec2 instance type')
    @click.option('--tm-release',
                  callback=cli_callbacks.create_release_url,
                  help='Treadmill release to use')
    @click.option('--app-root', default='/var/tmp',
                  show_default=True,
                  help='Treadmill app root')
    @click.option('--ldap-cidr-block', default='172.23.1.0/24',
                  show_default=True,
                  help='CIDR block for LDAP')
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
                                      'subnet_name',
                                      'instance_type',
                                      'tm_release',
                                      'app_root',
                                      'ipa_admin_password'
                                      'ldap_cidr_block'],
                  help="Options YAML file. ")
    @click.pass_context
    @cli.ON_CLI_EXCEPTIONS
    def configure_ldap(ctx, vpc_id, key, name, image, subnet_name, region,
                       instance_type, tm_release, app_root,
                       ldap_cidr_block, ipa_admin_password, manifest):
        """Configure Treadmill LDAP"""
        domain = ctx.obj['DOMAIN']
        proid = ctx.obj['PROID']

        if region:
            connection.Connection.context.region_name = region

        connection.Connection.context.domain = domain

        _ldap = ldap.LDAP(
            name=name,
            vpc_id=vpc_id,
        )

        _ldap.setup(
            key=key,
            count=1,
            image=image,
            instance_type=instance_type,
            tm_release=tm_release,
            app_root=app_root,
            cidr_block=ldap_cidr_block,
            ipa_admin_password=ipa_admin_password,
            proid=proid,
            subnet_name=subnet_name
        )

        click.echo(
            pprint(_ldap.subnet.show())
        )

    @configure.command(name='cell')
    @click.option('--vpc-name', 'vpc_id',
                  required=True,
                  callback=cli_callbacks.convert_to_vpc_id,
                  help='VPC Name')
    @click.option('--key', required=True, help='SSH Key Name')
    @click.option('--image', required=True,
                  help='Image to use for new instances e.g. RHEL-7.4')
    @click.option('--subnet-name', help='Cell(Subnet) Name',
                  required=True)
    @click.option('--count', default='3', type=int,
                  show_default=True,
                  help='Number of Treadmill masters to spin up')
    @click.option('--region', help='Region for the vpc')
    @click.option('--name', default='TreadmillMaster',
                  show_default=True,
                  help='Treadmill master name')
    @click.option('--instance-type',
                  default=constants.INSTANCE_TYPES['EC2']['micro'],
                  show_default=True,
                  help='AWS ec2 instance type')
    @click.option('--tm-release',
                  callback=cli_callbacks.create_release_url,
                  help='Treadmill release to use')
    @click.option('--app-root',
                  default='/var/tmp',
                  show_default=True,
                  help='Treadmill app root')
    @click.option('--cidr-block', default='172.23.0.0/24',
                  show_default=True,
                  help='CIDR block for the cell')
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
                                      'cidr_block',
                                      'cell_subnet_name',
                                      'ipa_admin_password'],
                  help="Options YAML file. ")
    @click.pass_context
    @cli.ON_CLI_EXCEPTIONS
    def configure_cell(ctx, vpc_id, key, image, subnet_name,
                       count, region, name, instance_type, tm_release,
                       app_root, cidr_block,
                       ipa_admin_password, manifest):
        """Configure Treadmill Cell"""
        domain = ctx.obj['DOMAIN']
        proid = ctx.obj['PROID']

        if region:
            connection.Connection.context.region_name = region

        connection.Connection.context.domain = domain

        _cell = cell.Cell(
            vpc_id=vpc_id,
            subnet_name=subnet_name
        )

        result = {}
        _cell.setup_zookeeper(
            name=constants.TREADMILL_ZOOKEEPER,
            key=key,
            count=count,
            image=image,
            instance_type=instance_type,
            subnet_cidr_block=cidr_block,
            ipa_admin_password=ipa_admin_password,
            proid=proid,
        )
        _cell.setup_master(
            name=name,
            key=key,
            count=count,
            image=image,
            instance_type=instance_type,
            tm_release=tm_release,
            app_root=app_root,
            subnet_cidr_block=cidr_block,
            ipa_admin_password=ipa_admin_password,
            proid=proid,
        )

        result['Cell'] = _cell.show()

        click.echo(
            pprint(result)
        )

    @configure.command(name='domain')
    @click.option('--vpc-name', 'vpc_id',
                  callback=cli_callbacks.convert_to_vpc_id,
                  required=True, help='VPC Name')
    @click.option('--key', required=True, help='SSH key name')
    @click.option('--image', required=True,
                  help='Image to use for new master instance e.g. RHEL-7.4')
    @click.option('--subnet-name', help='Subnet Name', required=True)
    @click.option('--name', default='TreadmillIPA',
                  show_default=True,
                  help='Name of the instance')
    @click.option('--region', help='Region for the vpc')
    @click.option('--subnet-cidr-block', help='Cidr block of subnet for IPA',
                  show_default=True,
                  default='172.23.2.0/24')
    @click.option('--count', help='Count of the instances',
                  show_default=True,
                  default=1)
    @click.option('--ipa-admin-password',
                  callback=cli_callbacks.validate_ipa_password,
                  envvar='TREADMILL_IPA_ADMIN_PASSWORD',
                  help='Password for IPA admin')
    @click.option('--tm-release',
                  callback=cli_callbacks.create_release_url,
                  help='Treadmill Release')
    @click.option('--instance-type',
                  default=constants.INSTANCE_TYPES['EC2']['medium'],
                  show_default=True,
                  help='Instance type')
    @click.option('-m', '--' + _OPTIONS_FILE,
                  cls=mutually_exclusive_option.MutuallyExclusiveOption,
                  mutually_exclusive=['region',
                                      'vpc_id',
                                      'name',
                                      'key',
                                      'count',
                                      'image',
                                      'instance_type',
                                      'tm_release',
                                      'subnet_cidr_block'
                                      'subnet_name',
                                      'ipa_admin_password'],
                  help="Options YAML file. ")
    @click.pass_context
    def configure_domain(ctx, vpc_id, key, image, subnet_name, name, region,
                         subnet_cidr_block, count, ipa_admin_password,
                         tm_release, instance_type, manifest):
        """Configure Treadmill Domain (IPA)"""

        domain = ctx.obj['DOMAIN']
        proid = ctx.obj['PROID']

        connection.Connection.context.domain = domain
        if region:
            connection.Connection.context.region_name = region

        if not ipa_admin_password:
            ipa_admin_password = os.environ.get(
                'TREADMILL_IPA_ADMIN_PASSWORD',
                click.prompt(
                    'Create IPA admin password ',
                    hide_input=True,
                    confirmation_prompt=True
                )
            )

        _ipa = ipa.IPA(name=name, vpc_id=vpc_id)

        _ipa.setup(
            count=count,
            ipa_admin_password=ipa_admin_password,
            tm_release=tm_release,
            key=key,
            instance_type=instance_type,
            image=image,
            cidr_block=subnet_cidr_block,
            proid=proid,
            subnet_name=subnet_name
        )

        click.echo(
            pprint(_ipa.show())
        )

    @configure.command(name='node')
    @click.option('--vpc-name', 'vpc_id',
                  callback=cli_callbacks.convert_to_vpc_id,
                  required=True, help='VPC Name')
    @click.option('--key', required=True, help='SSH Key Name')
    @click.option('--image', required=True,
                  help='Image to use for new node instance e.g. RHEL-7.4')
    @click.option('--subnet-name', required=True, help='Cell(Subnet) Name')
    @click.option('--region', help='Region for the vpc')
    @click.option('--name', default='TreadmillNode',
                  show_default=True,
                  help='Node name')
    @click.option('--instance-type',
                  default=constants.INSTANCE_TYPES['EC2']['large'],
                  show_default=True,
                  help='AWS ec2 instance type')
    @click.option('--tm-release',
                  callback=cli_callbacks.create_release_url,
                  help='Treadmill release to use')
    @click.option('--app-root', default='/var/tmp/treadmill-node',
                  show_default=True,
                  help='Treadmill app root')
    @click.option('--ipa-admin-password',
                  callback=cli_callbacks.ipa_password_prompt,
                  envvar='TREADMILL_IPA_ADMIN_PASSWORD',
                  help='Password for IPA admin')
    @click.option('--with-api', required=False, is_flag=True,
                  show_default=True,
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
                                      'subnet_name',
                                      'ipa_admin_password'
                                      'with_api'],
                  help="Options YAML file. ")
    @click.pass_context
    @cli.ON_CLI_EXCEPTIONS
    def configure_node(ctx, vpc_id, key, image, subnet_name, region, name,
                       instance_type, tm_release, app_root,
                       ipa_admin_password, with_api, manifest):
        """Configure new Node in Cell"""
        domain = ctx.obj['DOMAIN']
        proid = ctx.obj['PROID']

        connection.Connection.context.domain = domain
        if region:
            connection.Connection.context.region_name = region

        if not ipa_admin_password:
            ipa_admin_password = os.environ.get(
                'TREADMILL_IPA_ADMIN_PASSWORD',
                click.prompt('IPA admin password ', hide_input=True)
            )

        _node = node.Node(name, vpc_id)

        _node.setup(
            key=key,
            image=image,
            instance_type=instance_type,
            tm_release=tm_release,
            app_root=app_root,
            ipa_admin_password=ipa_admin_password,
            with_api=with_api,
            proid=proid,
            subnet_name=subnet_name
        )
        click.echo(
            pprint(_node.subnet.show())
        )

    @cloud.group()
    def delete():
        """Delete Treadmill EC2 Objects"""
        pass

    @delete.command(name='vpc')
    @click.option('--vpc-name', 'vpc_id',
                  callback=cli_callbacks.convert_to_vpc_id,
                  required=True, help='VPC Name')
    @click.pass_context
    @cli.ON_CLI_EXCEPTIONS
    def delete_vpc(ctx, vpc_id):
        """Delete VPC"""

        domain = ctx.obj['DOMAIN']
        connection.Connection.context.domain = domain

        vpc.VPC(id=vpc_id).delete()

    @delete.command(name='cell')
    @click.option('--vpc-name', 'vpc_id',
                  callback=cli_callbacks.convert_to_vpc_id,
                  required=True, help='VPC Name')
    @click.option('--subnet-name', required=True,
                  help='Subnet Name of cell')
    @click.pass_context
    @cli.ON_CLI_EXCEPTIONS
    def delete_cell(ctx, vpc_id, subnet_name):
        """Delete Cell (Subnet)"""
        connection.Connection.context.domain = ctx.obj['DOMAIN']

        subnet.Subnet(vpc_id=vpc_id, name=subnet_name).destroy()

    @delete.command(name='domain')
    @click.option('--vpc-name', 'vpc_id',
                  callback=cli_callbacks.convert_to_vpc_id,
                  required=True, help='VPC Name')
    @click.option('--subnet-name',
                  required=True, help='Subnet Name of Domain')
    @click.option('--name', help='Name of Instance',
                  show_default=True,
                  default="TreadmillIPA")
    @click.pass_context
    @cli.ON_CLI_EXCEPTIONS
    def delete_domain(ctx, vpc_id, subnet_name, name):
        """Delete IPA"""
        connection.Connection.context.domain = ctx.obj['DOMAIN']

        _ipa = ipa.IPA(name=name, vpc_id=vpc_id)
        _ipa.destroy(subnet_name=subnet_name)

    @delete.command(name='ldap')
    @click.option('--vpc-name', 'vpc_id',
                  callback=cli_callbacks.convert_to_vpc_id,
                  required=True, help='VPC Name')
    @click.option('--subnet-name',
                  help='Subnet Name of LDAP')
    @click.option('--name', help='Name of Instance',)
    @click.pass_context
    @cli.ON_CLI_EXCEPTIONS
    def delete_ldap(ctx, vpc_id, subnet_name, name):
        """Delete LDAP"""
        connection.Connection.context.domain = ctx.obj['DOMAIN']

        _ldap = ldap.LDAP(name=name, vpc_id=vpc_id)
        _ldap.destroy(subnet_name=subnet_name)

    @delete.command(name='node')
    @click.option('--vpc-name', 'vpc_id',
                  callback=cli_callbacks.convert_to_vpc_id,
                  required=True, help='VPC Name')
    @click.option('--name', help='Instance Name', required=False)
    @click.option('--instance-id', help='Instance ID', required=False)
    @click.pass_context
    @cli.ON_CLI_EXCEPTIONS
    def delete_node(ctx, vpc_id, name, instance_id):
        """Delete Node"""
        domain = ctx.obj['DOMAIN']
        if not name and not instance_id:
            _LOGGER.error('Provide either --name or --instance-id of'
                          'Node Instance and try again.')
            return

        connection.Connection.context.domain = domain
        _node = node.Node(name=name, vpc_id=vpc_id)
        _node.destroy(instance_id=instance_id)

    @cloud.group('list')
    def _list():
        """Show Treadmill Cloud Resources"""
        pass

    @_list.command(name='vpc')
    @click.option('--vpc-name', 'vpc_id',
                  callback=cli_callbacks.convert_to_vpc_id,
                  help='VPC Name')
    @click.pass_context
    @cli.ON_CLI_EXCEPTIONS
    def vpc_resources(ctx, vpc_id):
        """Show VPC(s)"""
        domain = ctx.obj['DOMAIN']
        connection.Connection.context.domain = domain
        if vpc_id:
            result = pprint(vpc.VPC(id=vpc_id).show())
            click.echo(result)
        else:
            _vpcs = vpc.VPC.all()
            result = list(map(lambda v: {'id': v.id, 'name': v.name}, _vpcs))
            click.echo({'Vpcs': result})

    @_list.command(name='cell')
    @click.option('--vpc-name', 'vpc_id',
                  callback=cli_callbacks.convert_to_vpc_id,
                  help='VPC Name')
    @click.option('--subnet-name',
                  help='Subnet Name of cell')
    @click.pass_context
    @cli.ON_CLI_EXCEPTIONS
    def cell_resources(ctx, vpc_id, subnet_name):
        """Show Cell"""
        domain = ctx.obj['DOMAIN']
        connection.Connection.context.domain = domain
        if subnet_name:
            click.echo(
                pprint(
                    subnet.Subnet(name=subnet_name, vpc_id=vpc_id).show()
                )
            )
            return

        if vpc_id:
            vpcs = [vpc_id]
        else:
            vpcs = [_vpc.id for _vpc in vpc.VPC.all()]

        result = []

        for v in vpcs:
            subnets = vpc.VPC(id=v).list_cells()
            if subnets:
                result.append({
                    'VpcId': v,
                    'Subnets': subnets
                })

        click.echo(pprint(result))

    @cloud.group()
    def port():
        """enable/disable EC2 instance port"""
        pass

    @port.command(name='enable')
    @click.option(
        '-a', '--anywhere', is_flag=True,
        default=True,
        show_default=True,
        help='From Anywhere?'
    )
    @click.option('--protocol', help='Protocol',
                  show_default=True,
                  default='tcp')
    @click.option('-p', '--port', required=True, help='Port')
    @click.option('-s', '--security-group-id', required=True,
                  help='Security Group ID')
    def enable_port(security_group_id, port, protocol, anywhere):
        """Enable Port from my ip"""
        security_group.enable(port, security_group_id, protocol, anywhere)

    @port.command(name='disable')
    @click.option(
        '-a', '--anywhere',
        is_flag=True,
        default=True,
        show_default=True,
        help='From Anywhere?'
    )
    @click.option('--protocol', help='Protocol',
                  show_default=True,
                  default='tcp')
    @click.option('-p', '--port', required=True, help='Port')
    @click.option('-s', '--security-group-id', required=True,
                  help='Security Group ID')
    def disable_port(security_group_id, port, protocol, anywhere):
        """Disable Port from my ip"""
        security_group.disable(port, security_group_id, protocol, anywhere)

    return cloud
