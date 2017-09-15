import os
import click
from pprint import pprint
import logging
import re
import pkg_resources

from treadmill.infra import constants, connection, vpc, subnet
from treadmill.infra.setup import ipa, ldap, node, cell
from treadmill.infra.utils import security_group


import yaml
from click import Option, UsageError

_LOGGER = logging.getLogger(__name__)

_OPTIONS_FILE = 'manifest'

_IPA_PASSWORD_RE = re.compile('.{8,}')
_URL_RE = re.compile('https?|www.*')


def init():
    """Cloud CLI module"""

    def _convert_to_vpc_id(ctx, param, value):
        """Returns VPC ID from Name"""
        if not value:
            return value
        vpc_id = vpc.VPC.get_id_from_name(value)
        if not vpc_id:
            raise click.BadParameter("VPC doesn't exist.")
        return vpc_id

    def _validate_vpc_name(ctx, param, value):
        _vpc_id = vpc.VPC.get_id_from_name(value)
        if _vpc_id:
            raise click.BadParameter(
                'VPC %s already exists with name: %s' %
                (_vpc_id, value)
            )
        else:
            return value

    def _convert_to_subnet_id(vpc_id, subnet_name):
        if not subnet_name:
            return subnet_name
        subnet_id = subnet.Subnet.get_subnet_id_from_name(vpc_id, subnet_name)
        if not subnet_id:
            raise click.BadParameter("Subnet doesn't exist.")
        return subnet_id

    def _validate_ipa_password(ctx, param, value):
        """IPA admin password validation"""
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

    def _create_release_url(ctx, param, value):
        """Treadmill current release version"""
        if value and _URL_RE.match(value):
            return value

        _build_url = lambda version: '{}/{}/treadmill'.format(
            constants.TREADMILL_DEFAULT_URL, version,
        )

        if value:
            return _build_url(value)

        version = None

        try:
            version = pkg_resources.resource_string(
                'treadmill',
                'VERSION.txt'
            )
        except Exception:
            pass

        if version:
            return _build_url(version.decode('utf-8').strip())
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
        if not connection.Connection.get_credentials():
            raise click.ClickException(
                'AWS credentials not specified.'
            )

        ctx.obj['DOMAIN'] = domain

    @cloud.group()
    @click.option('--proid', default='treadmld',
                  help='Proid user for treadmill')
    @click.pass_context
    def init(ctx, proid):
        """Initialize Treadmill EC2 Objects"""
        ctx.obj['PROID'] = proid

    @init.command(name='vpc')
    @click.option(
        '--name',
        required=True,
        help='VPC name',
        callback=_validate_vpc_name
    )
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
    @click.option('-m', '--' + _OPTIONS_FILE,
                  cls=MutuallyExclusiveOption,
                  mutually_exclusive=['region',
                                      'vpc_cidr_block',
                                      'secgroup_desc',
                                      'secgroup_name',
                                      'name'],
                  help="Options YAML file. ")
    @click.pass_context
    def init_vpc(ctx, region, vpc_cidr_block,
                 secgroup_name, secgroup_desc,
                 name, manifest):
        """Initialize Treadmill VPC"""
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

    @init.command(name='ldap')
    @click.option('--vpc-name', 'vpc_id',
                  required=True,
                  callback=_convert_to_vpc_id,
                  help='VPC name')
    @click.option('--key', required=True, help='SSH Key Name')
    @click.option('--image', required=True,
                  help='Image to use for instances e.g. RHEL-7.4')
    @click.option('--subnet-name', help='Subnet Name for LDAP',
                  required=True)
    @click.option('--count', default='1', type=int,
                  help='Number of Treadmill ldap instances to spin up')
    @click.option('--region', help='Region for the vpc')
    @click.option('--instance-type',
                  default=constants.INSTANCE_TYPES['EC2']['micro'],
                  help='AWS ec2 instance type')
    # TODO: Pick the current Treadmill release by default.
    @click.option('--tm-release',
                  callback=_create_release_url,
                  help='Treadmill release to use')
    @click.option('--ldap-hostname', default='treadmillldap1',
                  help='LDAP hostname')
    @click.option('--app-root', default='/var/tmp',
                  help='Treadmill app root')
    @click.option('--ldap-cidr-block', default='172.23.1.0/24',
                  help='CIDR block for LDAP')
    @click.option('--ipa-admin-password', callback=_ipa_password_prompt,
                  envvar='TREADMILL_IPA_ADMIN_PASSWORD',
                  help='Password for IPA admin')
    @click.option('-m', '--' + _OPTIONS_FILE,
                  cls=MutuallyExclusiveOption,
                  mutually_exclusive=['region',
                                      'vpc_name',
                                      'key',
                                      'count',
                                      'image',
                                      'instance_type',
                                      'tm_release',
                                      'ldap_hostname',
                                      'app_root',
                                      'subnet_name',
                                      'ipa_admin_password'
                                      'ldap_cidr_block'],
                  help="Options YAML file. ")
    @click.pass_context
    def init_ldap(ctx, vpc_id, key, image, subnet_name, count, region,
                  instance_type, tm_release, ldap_hostname, app_root,
                  ldap_cidr_block, ipa_admin_password, manifest):
        """Initialize Treadmill LDAP"""
        domain = ctx.obj['DOMAIN']
        proid = ctx.obj['PROID']

        if region:
            connection.Connection.context.region_name = region

        connection.Connection.context.domain = domain

        _ldap = ldap.LDAP(
            name='TreadmillLDAP',
            vpc_id=vpc_id,
        )

        subnet_id = subnet.Subnet.get_subnet_id_from_name(vpc_id, subnet_name)

        _ldap.setup(
            key=key,
            count=1,
            image=image,
            instance_type=instance_type,
            tm_release=tm_release,
            app_root=app_root,
            ldap_hostname=ldap_hostname,
            cidr_block=ldap_cidr_block,
            subnet_id=subnet_id,
            ipa_admin_password=ipa_admin_password,
            proid=proid,
            subnet_name=subnet_name
        )

        click.echo(
            pprint(_ldap.subnet.show())
        )

    @init.command(name='cell')
    @click.option('--vpc-name', 'vpc_id',
                  required=True,
                  callback=_convert_to_vpc_id,
                  help='VPC Name')
    @click.option('--key', required=True, help='SSH Key Name')
    @click.option('--image', required=True,
                  help='Image to use for new instances e.g. RHEL-7.4')
    @click.option('--cell-subnet-name', help='Cell Subnet Name',
                  required=True)
    @click.option('--count', default='3', type=int,
                  help='Number of Treadmill masters to spin up')
    @click.option('--region', help='Region for the vpc')
    @click.option('--name', default='TreadmillMaster',
                  help='Treadmill master name')
    @click.option('--instance-type',
                  default=constants.INSTANCE_TYPES['EC2']['micro'],
                  help='AWS ec2 instance type')
    # TODO: Pick the current Treadmill release by default.
    @click.option('--tm-release',
                  callback=_create_release_url,
                  help='Treadmill release to use')
    @click.option('--ldap-hostname', default='treadmillldap1',
                  help='LDAP hostname')
    @click.option('--app-root', default='/var/tmp', help='Treadmill app root')
    @click.option('--cell-cidr-block', default='172.23.0.0/24',
                  help='CIDR block for the cell')
    @click.option('--ldap-cidr-block', default='172.23.1.0/24',
                  help='CIDR block for LDAP')
    @click.option('--ldap-subnet-name',
                  help='Subnet Name for Cell')
    @click.option('--without-ldap', required=False, is_flag=True,
                  default=False, help='Flag for LDAP Server')
    @click.option('--ipa-admin-password', callback=_ipa_password_prompt,
                  envvar='TREADMILL_IPA_ADMIN_PASSWORD',
                  help='Password for IPA admin')
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
                                      'ldap_hostname',
                                      'app_root',
                                      'cell_cidr_block'
                                      'ldap_subnet_name',
                                      'cell_subnet_name',
                                      'ipa_admin_password',
                                      'without_ldap',
                                      'ldap_cidr_block'],
                  help="Options YAML file. ")
    @click.pass_context
    def init_cell(ctx, vpc_id, key, image, cell_subnet_name, count, region,
                  name, instance_type, tm_release, ldap_hostname, app_root,
                  cell_cidr_block, ldap_cidr_block, ldap_subnet_name,
                  without_ldap, ipa_admin_password, manifest):
        """Initialize Treadmill Cell"""
        domain = ctx.obj['DOMAIN']
        proid = ctx.obj['PROID']

        if region:
            connection.Connection.context.region_name = region

        connection.Connection.context.domain = domain

        subnet_id = subnet.Subnet.get_subnet_id_from_name(
            vpc_id, cell_subnet_name
        )

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

            ldap_subnet_id = subnet.Subnet.get_subnet_id_from_name(
                vpc_id, ldap_subnet_name
            )

            _ldap.setup(
                key=key,
                count=1,
                image=image,
                instance_type=instance_type,
                tm_release=tm_release,
                app_root=app_root,
                ldap_hostname=ldap_hostname,
                cidr_block=ldap_cidr_block,
                subnet_id=ldap_subnet_id,
                ipa_admin_password=ipa_admin_password,
                proid=proid,
                subnet_name=ldap_subnet_name
            )

            result['Ldap'] = _ldap.subnet.show()

        _cell.setup_zookeeper(
            name='TreadmillZookeeper',
            key=key,
            image=image,
            instance_type=instance_type,
            subnet_cidr_block=cell_cidr_block,
            ldap_hostname=ldap_hostname,
            ipa_admin_password=ipa_admin_password,
            proid=proid,
            subnet_name=cell_subnet_name
        )
        _cell.setup_master(
            name=name,
            key=key,
            count=count,
            image=image,
            instance_type=instance_type,
            tm_release=tm_release,
            ldap_hostname=ldap_hostname,
            app_root=app_root,
            subnet_cidr_block=cell_cidr_block,
            ipa_admin_password=ipa_admin_password,
            proid=proid,
            subnet_name=cell_subnet_name
        )

        result['Cell'] = _cell.show()

        click.echo(
            pprint(result)
        )

    @init.command(name='domain')
    @click.option('--vpc-name', 'vpc_id',
                  callback=_convert_to_vpc_id,
                  required=True, help='VPC Name')
    @click.option('--key', required=True, help='SSH key name')
    @click.option('--image', required=True,
                  help='Image to use for new master instance e.g. RHEL-7.4')
    @click.option('--subnet-name', help='Subnet Name', required=True)
    @click.option('--name', default='TreadmillIPA',
                  help='Name of the instance')
    @click.option('--region', help='Region for the vpc')
    @click.option('--subnet-cidr-block', help='Cidr block of subnet for IPA',
                  default='172.23.2.0/24')
    @click.option('--count', help='Count of the instances', default=1)
    @click.option('--ipa-admin-password', callback=_validate_ipa_password,
                  envvar='TREADMILL_IPA_ADMIN_PASSWORD',
                  help='Password for IPA admin')
    @click.option('--tm-release',
                  callback=_create_release_url,
                  help='Treadmill Release')
    @click.option('--instance-type',
                  default=constants.INSTANCE_TYPES['EC2']['medium'],
                  help='Instance type')
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
                                      'subnet_name',
                                      'ipa_admin_password'],
                  help="Options YAML file. ")
    @click.pass_context
    def init_domain(ctx, vpc_id, key, image, subnet_name, name, region,
                    subnet_cidr_block, count, ipa_admin_password, tm_release,
                    instance_type, manifest):
        """Initialize Treadmill Domain (IPA)"""

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

        subnet_id = subnet.Subnet.get_subnet_id_from_name(vpc_id, subnet_name)

        _ipa.setup(
            subnet_id=subnet_id,
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

    @init.command(name='node')
    @click.option('--vpc-name', 'vpc_id',
                  callback=_convert_to_vpc_id,
                  required=True, help='VPC Name')
    @click.option('--key', required=True, help='SSH Key Name')
    @click.option('--image', required=True,
                  help='Image to use for new node instance e.g. RHEL-7.4')
    @click.option('--subnet-name', required=True, help='Subnet Name')
    @click.option('--region', help='Region for the vpc')
    @click.option('--name', default='TreadmillNode',
                  help='Node name')
    @click.option('--count', default='1', type=int,
                  help='Number of Treadmill nodes to spin up')
    @click.option('--instance-type',
                  default=constants.INSTANCE_TYPES['EC2']['large'],
                  help='AWS ec2 instance type')
    @click.option('--tm-release',
                  callback=_create_release_url,
                  help='Treadmill release to use')
    @click.option('--ldap-hostname', default='treadmillldap1',
                  help='LDAP hostname')
    @click.option('--app-root', default='/var/tmp/treadmill-node',
                  help='Treadmill app root')
    @click.option('--ipa-admin-password', callback=_ipa_password_prompt,
                  envvar='TREADMILL_IPA_ADMIN_PASSWORD',
                  help='Password for IPA admin')
    @click.option('--with-api', required=False, is_flag=True,
                  default=False, help='Provision node with Treadmill APIs')
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
                                      'ldap_hostname',
                                      'app_root',
                                      'subnet_name',
                                      'ipa_admin_password'
                                      'with_api'],
                  help="Options YAML file. ")
    @click.pass_context
    def init_node(ctx, vpc_id, key, image, subnet_name, region, name, count,
                  instance_type, tm_release, ldap_hostname, app_root,
                  ipa_admin_password, with_api, manifest):
        """Initialize new Node in Cell"""

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

        subnet_id = subnet.Subnet.get_subnet_id_from_name(vpc_id, subnet_name)

        if not subnet_id:
            raise click.BadParameter(
                "Subnet doesn't exist with name %s",
                subnet_name
            )

        _node.setup(
            key=key,
            count=count,
            image=image,
            instance_type=instance_type,
            tm_release=tm_release,
            app_root=app_root,
            ldap_hostname=ldap_hostname,
            subnet_id=subnet_id,
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
    @click.option('--subnet-name', required=True,
                  help='Subnet Name of cell')
    @click.pass_context
    def delete_cell(ctx, vpc_id, subnet_name):
        """Delete Cell (Subnet)"""
        subnet_id = _convert_to_subnet_id(vpc_id, subnet_name)
        domain = ctx.obj['DOMAIN']
        connection.Connection.context.domain = domain
        subnet.Subnet(id=subnet_id).destroy()

    @delete.command(name='domain')
    @click.option('--vpc-name', 'vpc_id',
                  callback=_convert_to_vpc_id,
                  required=True, help='VPC Name')
    @click.option('--subnet-name',
                  required=True, help='Subnet Name of Domain')
    @click.option('--name', help='Name of Instance',
                  default="TreadmillIPA")
    @click.pass_context
    def delete_domain(ctx, vpc_id, subnet_name, name):
        """Delete IPA"""
        subnet_id = _convert_to_subnet_id(vpc_id, subnet_name)
        domain = ctx.obj['DOMAIN']
        connection.Connection.context.domain = domain

        _ipa = ipa.IPA(name=name, vpc_id=vpc_id)
        _ipa.destroy(subnet_id=subnet_id)

    @delete.command(name='ldap')
    @click.option('--vpc-name', 'vpc_id',
                  callback=_convert_to_vpc_id,
                  required=True, help='VPC Name')
    @click.option('--subnet-name', required=True,
                  help='Subnet Name of LDAP')
    @click.option('--name', help='Name of Instance',
                  default="TreadmillLDAP")
    @click.pass_context
    def delete_ldap(ctx, vpc_id, subnet_name, name):
        """Delete LDAP"""
        subnet_id = _convert_to_subnet_id(vpc_id, subnet_name)
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

    @cloud.group()
    def list():
        """Show Treadmill Cloud Resources"""
        pass

    @list.command(name='vpc')
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

    @list.command(name='cell')
    @click.option('--vpc-name', 'vpc_id',
                  callback=_convert_to_vpc_id,
                  help='VPC Name')
    @click.option('--subnet-name',
                  help='Subnet Name of cell')
    @click.pass_context
    def cell_resources(ctx, vpc_id, subnet_name):
        """Show Cell"""
        subnet_id = _convert_to_subnet_id(vpc_id, subnet_name)
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
            vpcs = [vpc.id for vpc in vpc.VPC.all()]

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
    @click.option('-p', '--port', required=True, help='Port')
    @click.option('-s', '--security-group-id', required=True,
                  help='Security Group ID')
    @click.option('--protocol', help='Protocol', default='tcp')
    def enable_port(port, security_group_id, protocol):
        """Enable Port from my ip"""
        security_group.enable(port, security_group_id, protocol)

    @port.command(name='disable')
    @click.option('-p', '--port', required=True, help='Port')
    @click.option('-s', '--security-group-id', required=True,
                  help='Security Group ID')
    @click.option('--protocol', help='Protocol', default='tcp')
    def disable_port(port, security_group_id, protocol):
        """Disable Port from my ip"""
        security_group.disable(port, security_group_id, protocol)

    return cloud
