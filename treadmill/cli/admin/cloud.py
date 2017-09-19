import os
import click
from pprint import pprint
import logging
import re
import pkg_resources

from treadmill import cli
from treadmill import restclient
from treadmill.infra import constants, connection, vpc, subnet
from treadmill.infra.setup import ipa, ldap, node, cell
from treadmill.infra.utils import security_group, hosted_zones


import yaml
from click import Option, UsageError

_LOGGER = logging.getLogger(__name__)

_OPTIONS_FILE = 'manifest'

_IPA_PASSWORD_RE = re.compile('.{8,}')


def init():
    """Cloud CLI module"""

    def _convert_to_vpc_id(ctx, param, value):
        """Returns VPC ID from Name"""
        if not value:
            return value

        return vpc.VPC.get_id_from_name(value)

    def _validate_vpc_name(ctx, param, value):
        _vpc_id = vpc.VPC.get_id_from_name(value)
        if _vpc_id:
            raise click.BadParameter(
                'VPC %s already exists with name: %s' %
                (_vpc_id, value)
            )
        else:
            return value

    def _validate_ipa_password(ctx, param, value):
        """IPA admin password valdiation"""
        value = value or click.prompt(
            'IPA admin password ', hide_input=True, confirmation_prompt=True
        )
        if not _IPA_PASSWORD_RE.match(value):
            raise click.BadParameter(
                'Password must be greater than 8 characters.'
            )
        return value

    def _validate_domain(ctx, param, value):
        """Cloud domain validation"""

        if value.count(".") != 1:
            raise click.BadParameter('Valid domain like example.com')

        return value

    def _ipa_password_prompt(ctx, param, value):
        """IPA admin password prompt"""
        return value or click.prompt('IPA admin password ', hide_input=True)

    def _current_release_version(ctx, param, value):
        """Treadmill current release version"""
        version = None

        try:
            version = pkg_resources.resource_string(
                'treadmill',
                'VERSION.txt'
            )
        except Exception:
            pass

        if version:
            return version.decode('utf-8').strip()
        else:
            raise click.BadParameter('No version specified in VERSION.txt')

    class MutuallyExclusiveOption(Option):
        def __init__(self, *args, **kwargs):
            self.mutually_exclusive = set(kwargs.pop('mutually_exclusive', []))
            help = kwargs.get('help', '')
            if self.mutually_exclusive:
                ex_str = ', '.join(self.mutually_exclusive)
                kwargs['help'] = help + (
                    ' NOTE: This argument is mutually exclusive with'
                    ' arguments: [' + ex_str + '].'
                )
            super().__init__(*args, **kwargs)

        def handle_parse_result(self, ctx, opts, args):
            if self.mutually_exclusive.intersection(opts) and \
               self.name in opts:
                raise UsageError(
                    "Illegal usage: `{}` is mutually exclusive with "
                    "arguments `{}`.".format(
                        self.name,
                        ', '.join(self.mutually_exclusive)
                    )
                )
            if self.name == _OPTIONS_FILE and self.name in opts:
                _file = opts.pop(_OPTIONS_FILE)
                for _param in ctx.command.params:
                    opts[_param.name] = _param.default or \
                        _param.value_from_envvar(ctx) or ''
                with open(_file, 'r') as stream:
                    data = yaml.load(stream)

                _command_name = ctx.command.name
                if data.get(_command_name, None):
                    opts.update(data[_command_name])
                else:
                    raise click.BadParameter(
                        'Manifest file should have %s scope' % _command_name
                    )
                opts['vpc_id'] = opts.pop('vpc_name')
                ctx.params = opts

            return super().handle_parse_result(ctx, opts, args)

    @click.group()
    @click.option('--domain', required=True,
                  envvar='TREADMILL_DNS_DOMAIN',
                  callback=_validate_domain,
                  help='Domain for hosted zone')
    @click.pass_context
    def cloud(ctx, domain):
        """Manage Treadmill on cloud"""
        ctx.obj['DOMAIN'] = domain

    @cloud.group()
    def configure():
        """Configure Treadmill EC2 Objects"""
        pass

    @configure.command(name='vpc')
    @click.option('--region', help='Region for the vpc')
    @click.option('--vpc-cidr-block', default='172.23.0.0/16',
                  help='CIDR block for the vpc')
    @click.option('--secgroup_name', default='sg_common',
                  help='Security group name')
    @click.option(
        '--secgroup_desc',
        default='Treadmill Security Group',
        help='Description for the security group'
    )
    @click.option(
        '--name',
        required=True,
        help='VPC name',
        callback=_validate_vpc_name
    )
    @click.option('-m', '--' + _OPTIONS_FILE,
                  cls=MutuallyExclusiveOption,
                  mutually_exclusive=['region',
                                      'vpc_cidr_block',
                                      'secgroup_desc',
                                      'secgroup_name',
                                      'name'],
                  help="Options YAML file. ")
    @click.pass_context
    def configure_vpc(ctx, region, vpc_cidr_block,
                      secgroup_name, secgroup_desc,
                      name, manifest):
        """Configure Treadmill VPC"""
        domain = ctx.obj['DOMAIN']

        if region:
            connection.Connection.context.region_name = region

        connection.Connection.context.domain = domain

        _vpc = vpc.VPC.setup(
            name=name,
            cidr_block=vpc_cidr_block,
            secgroup_name=secgroup_name,
            secgroup_desc=secgroup_desc
        )

        click.echo(
            pprint(_vpc.show())
        )

    @configure.command(name='ldap')
    @click.option('--vpc-name', 'vpc_id',
                  required=True,
                  callback=_convert_to_vpc_id,
                  help='VPC name')
    @click.option('--region', help='Region for the vpc')
    @click.option('--key', required=True, help='SSH Key Name')
    @click.option('--image', required=True,
                  help='Image to use for instances e.g. RHEL-7.4')
    @click.option('--instance-type',
                  default=constants.INSTANCE_TYPES['EC2']['micro'],
                  help='AWS ec2 instance type')
    @click.option('--tm-release',
                  callback=_current_release_version,
                  help='Treadmill release to use')
    @click.option('--app-root', default='/var/tmp',
                  help='Treadmill app root')
    @click.option('--ldap-cidr-block', default='172.23.1.0/24',
                  help='CIDR block for LDAP')
    @click.option('--ldap-subnet-id', help='Subnet ID for LDAP')
    @click.option('--cell-subnet-id', help='Subnet ID of Cell',
                  required=True)
    @click.option('--ipa-admin-password', callback=_ipa_password_prompt,
                  envvar='TREADMILL_IPA_ADMIN_PASSWORD',
                  help='Password for IPA admin')
    @click.option('-m', '--' + _OPTIONS_FILE,
                  cls=MutuallyExclusiveOption,
                  mutually_exclusive=['region',
                                      'vpc_name',
                                      'key',
                                      'image',
                                      'instance_type',
                                      'tm_release',
                                      'app_root',
                                      'ldap_subnet_id',
                                      'cell_subnet_id',
                                      'ipa_admin_password'
                                      'ldap_cidr_block'],
                  help="Options YAML file. ")
    @click.pass_context
    def configure_ldap(ctx, vpc_id, region, key, image,
                       instance_type, tm_release, app_root,
                       ldap_cidr_block, ldap_subnet_id, cell_subnet_id,
                       ipa_admin_password, manifest):
        """Configure Treadmill LDAP"""
        domain = ctx.obj['DOMAIN']
        if region:
            connection.Connection.context.region_name = region

        connection.Connection.context.domain = domain

        _ldap = ldap.LDAP(
            name='TreadmillLDAP',
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
            cell_subnet_id=cell_subnet_id,
            subnet_id=ldap_subnet_id,
            ipa_admin_password=ipa_admin_password,
        )

        click.echo(
            pprint(_ldap.subnet.show())
        )

    @configure.command(name='cell')
    @click.option('--vpc-name', 'vpc_id',
                  required=True,
                  callback=_convert_to_vpc_id,
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
                  callback=_current_release_version,
                  help='Treadmill release to use')
    @click.option('--app-root', default='/var/tmp', help='Treadmill app root')
    @click.option('--cell-cidr-block', default='172.23.0.0/24',
                  help='CIDR block for the cell')
    @click.option('--ldap-cidr-block', default='172.23.1.0/24',
                  help='CIDR block for LDAP')
    @click.option('--subnet-id', help='Subnet ID')
    @click.option('--ldap-subnet-id',
                  help='Subnet ID for LDAP')
    @click.option('--without-ldap', required=False, is_flag=True,
                  default=False, help='Flag for LDAP Server')
    @click.option('--ipa-admin-password', callback=_ipa_password_prompt,
                  envvar='TREADMILL_IPA_ADMIN_PASSWORD',
                  help='Password for IPA admin')
    @click.option('-m', '--' + _OPTIONS_FILE,
                  cls=MutuallyExclusiveOption,
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
                                      'ldap_subnet_id',
                                      'subnet_id',
                                      'ipa_admin_password',
                                      'without_ldap',
                                      'ldap_cidr_block'],
                  help="Options YAML file. ")
    @click.pass_context
    def configure_cell(ctx, vpc_id, region, name, key, count, image,
                       instance_type, tm_release, app_root,
                       cell_cidr_block, ldap_cidr_block,
                       subnet_id, ldap_subnet_id,
                       without_ldap, ipa_admin_password, manifest):
        """Configure Treadmill Cell"""
        domain = ctx.obj['DOMAIN']

        if region:
            connection.Connection.context.region_name = region

        connection.Connection.context.domain = domain

        _cell = cell.Cell(
            vpc_id=vpc_id,
            subnet_id=subnet_id,
        )

        result = {}
        if not without_ldap:
            _ldap = ldap.LDAP(
                name='TreadmillLDAP',
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
                cell_subnet_id=_cell.id,
                subnet_id=ldap_subnet_id,
                ipa_admin_password=ipa_admin_password,
            )

            result['Ldap'] = _ldap.subnet.show()

        _cell.setup_zookeeper(
            name='TreadmillZookeeper',
            key=key,
            count=count,
            image=image,
            instance_type=instance_type,
            subnet_cidr_block=cell_cidr_block,
            ipa_admin_password=ipa_admin_password
        )

        _cell.setup_master(
            name=name,
            key=key,
            count=count,
            image=image,
            instance_type=instance_type,
            tm_release=tm_release,
            app_root=app_root,
            subnet_cidr_block=cell_cidr_block,
            ipa_admin_password=ipa_admin_password
        )

        result['Cell'] = _cell.show()

        click.echo(
            pprint(result)
        )

    @configure.command(name='domain')
    @click.option('--name', default='TreadmillIPA',
                  help='Name of the instance')
    @click.option('--region', help='Region for the vpc')
    @click.option('--vpc-name', 'vpc_id',
                  callback=_convert_to_vpc_id,
                  required=True, help='VPC Name')
    @click.option('--subnet-cidr-block', help='Cidr block of subnet for IPA',
                  default='172.23.2.0/24')
    @click.option('--subnet-id', help='Subnet ID')
    @click.option('--count', help='Count of the instances', default=1)
    @click.option('--ipa-admin-password', callback=_validate_ipa_password,
                  envvar='TREADMILL_IPA_ADMIN_PASSWORD',
                  help='Password for IPA admin')
    @click.option('--tm-release',
                  callback=_current_release_version,
                  help='Treadmill Release')
    @click.option('--key', required=True, help='SSH key name')
    @click.option('--instance-type',
                  default=constants.INSTANCE_TYPES['EC2']['medium'],
                  help='Instance type')
    @click.option('--image', required=True,
                  help='Image to use for new master instance e.g. RHEL-7.4')
    @click.option('-m', '--' + _OPTIONS_FILE,
                  cls=MutuallyExclusiveOption,
                  mutually_exclusive=['region',
                                      'vpc_id',
                                      'name',
                                      'key',
                                      'count',
                                      'image',
                                      'instance_type',
                                      'tm_release',
                                      'subnet_cidr_block'
                                      'subnet_id',
                                      'ipa_admin_password'],
                  help="Options YAML file. ")
    @click.pass_context
    def configure_domain(ctx, name, region, vpc_id,
                         subnet_cidr_block, subnet_id,
                         count, ipa_admin_password, tm_release, key,
                         instance_type, image, manifest):
        """Configure Treadmill Domain (IPA)"""

        domain = ctx.obj['DOMAIN']

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
            subnet_id=subnet_id,
            count=count,
            ipa_admin_password=ipa_admin_password,
            tm_release=tm_release,
            key=key,
            instance_type=instance_type,
            image=image,
            cidr_block=subnet_cidr_block,
        )

        click.echo(
            pprint(_ipa.show())
        )

    @configure.command(name='node')
    @click.option('--vpc-name', 'vpc_id',
                  callback=_convert_to_vpc_id,
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
                  callback=_current_release_version,
                  help='Treadmill release to use')
    @click.option('--app-root', default='/var/tmp/treadmill-node',
                  help='Treadmill app root')
    @click.option('--subnet-id', required=True, help='Subnet ID')
    @click.option('--ipa-admin-password', callback=_ipa_password_prompt,
                  envvar='TREADMILL_IPA_ADMIN_PASSWORD',
                  help='Password for IPA admin')
    @click.option('--with-api', required=False, is_flag=True,
                  default=False, help='Provision node with Treadmill APIs')
    @click.option('-m', '--' + _OPTIONS_FILE,
                  cls=MutuallyExclusiveOption,
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
    @click.pass_context
    def configure_node(ctx, vpc_id, region, name, key, image,
                       instance_type, tm_release, app_root,
                       subnet_id, ipa_admin_password, with_api, manifest):
        """Configure new Node in Cell"""

        domain = ctx.obj['DOMAIN']

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
            subnet_id=subnet_id,
            ipa_admin_password=ipa_admin_password,
            with_api=with_api,
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
                  callback=_convert_to_vpc_id,
                  required=True, help='VPC Name')
    @click.pass_context
    def delete_vpc(ctx, vpc_id):
        """Delete VPC"""

        domain = ctx.obj['DOMAIN']
        connection.Connection.context.domain = domain

        vpc.VPC(id=vpc_id).delete()

    @delete.command(name='cell')
    @click.option('--vpc-name', 'vpc_id',
                  callback=_convert_to_vpc_id,
                  required=True, help='VPC Name')
    @click.option('--subnet-id', required=True, help='Subnet ID of cell')
    @click.pass_context
    def delete_cell(ctx, vpc_id, subnet_id):
        """Delete Cell (Subnet)"""
        domain = ctx.obj['DOMAIN']
        connection.Connection.context.domain = domain
        subnet.Subnet(id=subnet_id).destroy()

    @delete.command(name='domain')
    @click.option('--vpc-name', 'vpc_id',
                  callback=_convert_to_vpc_id,
                  required=True, help='VPC Name')
    @click.option('--subnet-id', required=True, help='Subnet ID of IPA')
    @click.option('--name', help='Name of Instance',
                  default="TreadmillIPA")
    @click.pass_context
    def delete_domain(ctx, vpc_id, subnet_id, name):
        """Delete IPA"""
        domain = ctx.obj['DOMAIN']
        connection.Connection.context.domain = domain

        _ipa = ipa.IPA(name=name, vpc_id=vpc_id)
        _ipa.destroy(subnet_id=subnet_id)

    @delete.command(name='ldap')
    @click.option('--vpc-name', 'vpc_id',
                  callback=_convert_to_vpc_id,
                  required=True, help='VPC Name')
    @click.option('--subnet-id', required=True, help='Subnet ID of LDAP')
    @click.option('--name', help='Name of Instance',
                  default="TreadmillLDAP")
    @click.pass_context
    def delete_ldap(ctx, vpc_id, subnet_id, name):
        """Delete LDAP"""
        domain = ctx.obj['DOMAIN']
        connection.Connection.context.domain = domain

        _ldap = ldap.LDAP(name=name, vpc_id=vpc_id)
        _ldap.destroy(subnet_id=subnet_id)

    @delete.command(name='node')
    @click.option('--vpc-name', 'vpc_id',
                  callback=_convert_to_vpc_id,
                  required=True, help='VPC Name')
    @click.option('--name', help='Instance Name', required=False)
    @click.option('--instance-id', help='Instance ID', required=False)
    @click.pass_context
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
                  callback=_convert_to_vpc_id,
                  help='VPC Name')
    @click.pass_context
    def vpc_resources(ctx, vpc_id):
        """Show VPC(s)"""
        domain = ctx.obj['DOMAIN']
        connection.Connection.context.domain = domain
        if vpc_id:
            result = pprint(vpc.VPC(id=vpc_id).show())
        else:
            _vpcs = vpc.VPC.all()
            result = map(lambda v: v.id + "\t:\t" + v.name, _vpcs)
            result = "\n".join(result)

        click.echo(result)

    @_list.command(name='cell')
    @click.option('--vpc-name', 'vpc_id',
                  callback=_convert_to_vpc_id,
                  help='VPC Name')
    @click.option('--subnet-id', help='Subnet ID of cell')
    @click.pass_context
    def cell_resources(ctx, vpc_id, subnet_id):
        """Show Cell"""
        domain = ctx.obj['DOMAIN']
        connection.Connection.context.domain = domain
        if subnet_id:
            click.echo(
                pprint(
                    subnet.Subnet(id=subnet_id).show()
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
    @click.option('--protocol', help='Protocol', default='tcp')
    @click.option('-p', '--port', required=True, help='Port')
    @click.option('-s', '--security-group-id', required=True,
                  help='Security Group ID')
    def enable_port(security_group_id, port, protocol):
        """Enable Port from my ip"""
        security_group.enable(port, security_group_id, protocol)

    @port.command(name='disable')
    @click.option('--protocol', help='Protocol', default='tcp')
    @click.option('-p', '--port', required=True, help='Port')
    @click.option('-s', '--security-group-id', required=True,
                  help='Security Group ID')
    def disable_port(security_group_id, port, protocol):
        """Disable Port from my ip"""
        security_group.disable(port, security_group_id, protocol)

    @cloud.command(name='delete-hosted-zone')
    @click.option('--zones-to-retain', required=True,
                  help='Hosted Zone IDs to retain', multiple=True)
    def delete_hosted_zones(zones_to_retain):
        """Delete Hosted Zones"""
        hosted_zones.delete_obsolete(zones_to_retain)

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
                url='/user',
                payload={'username': username},
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
            url='/user',
            payload={'username': username},
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
                url='/host',
                payload={'hostname': hostname},
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
                url='/host',
                payload={'hostname': hostname},
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
                api=ctx.obj.get('api'),
                url='/service',
                payload={
                    'service': service,
                    'domain': ctx.obj.get('DOMAIN'),
                    'hostname': hostname
                },
                headers={'Content-Type': 'application/json'}
            ).content
        )

    return cloud
