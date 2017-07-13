import click
from pprint import pprint
from treadmill.infra.setup.cell import Cell
from treadmill.infra.setup.ipa import IPA
from treadmill.infra import constants, connection, vpc, subnet
from treadmill.infra.setup import ldap


def init():
    """Cloud CLI module"""
    @click.group()
    def cloud():
        """Manage treadmill on cloud"""
        pass

    @cloud.command(name='init')
    @click.option('--domain', required=False, default=constants.DEFAULT_DOMAIN,
                  help='Domain for hosted zone')
    @click.option('--region', required=False,
                  help='Region for the vpc')
    @click.option('--vpc-cidr-block', required=False,
                  default='172.23.0.0/16', help='CIDR block for the vpc')
    @click.option('--secgroup_name', required=False,
                  default='sg_common', help='Security group name')
    @click.option(
        '--secgroup_desc',
        required=False,
        default='Treadmill Security Group',
        help='Description for the security group')
    def init(domain, region, vpc_cidr_block,
             secgroup_name, secgroup_desc):
        """Initialize treadmill VPC"""
        if region:
            connection.Connection.region_name = region

        _vpc = vpc.VPC.setup(
            domain=domain,
            cidr_block=vpc_cidr_block,
            secgroup_name=secgroup_name,
            secgroup_desc=secgroup_desc
        )

        click.echo(
            pprint(_vpc.show())
        )

    @cloud.command(name='init-cell')
    @click.option('--vpc-id', required=True, help='VPC ID of cell')
    @click.option('--region', required=False, help='Region for the vpc')
    @click.option('--domain', required=False,
                  default=constants.DEFAULT_DOMAIN,
                  help='Domain for hosted zone')
    @click.option('--name', required=False, default='TreadmillMaster',
                  help='Treadmill master name')
    @click.option('--key', required=True, help='SSH Key Name')
    @click.option('--count', required=True, default='3', type=int,
                  help='Number of treadmill masters to spin up')
    @click.option('--image-id', required=True,
                  help='AMI ID to use for new master instance')
    @click.option('--instance-type', required=True,
                  default=constants.INSTANCE_TYPES['EC2']['micro'],
                  help='AWS ec2 instance type')
    # TODO: Pick the current treadmill release by default.
    @click.option('--tm-release', required=True,
                  default='0.1.0', help='Treadmill release to use')
    @click.option('--ldap-hostname', required=True,
                  default='ldapserver', help='LDAP hostname')
    @click.option('--app-root', required=True,
                  default='/var/tmp/', help='Treadmill app root')
    @click.option('--cell-cidr-block', required=False,
                  default='172.23.0.0/24', help='CIDR block for the cell')
    @click.option('--ldap-cidr-block', required=False,
                  default='172.23.1.0/24', help='CIDR block for LDAP')
    @click.option('--subnet-id', required=False, help='Subnet ID')
    @click.option('--ldap-subnet-id', required=False,
                  help='Subnet ID for LDAP')
    def init_cell(vpc_id, region, domain, name, key, count, image_id,
                  instance_type, tm_release, ldap_hostname, app_root,
                  cell_cidr_block, ldap_cidr_block, subnet_id, ldap_subnet_id):
        """Initialize treadmill cell"""
        if region:
            connection.Connection.region_name = region

        cell = Cell(
            domain=domain,
            vpc_id=vpc_id,
            subnet_id=subnet_id,
        )

        cell.setup_zookeeper(
            name='TreadmillZookeeper',
            key=key,
            image_id=image_id,
            instance_type=instance_type,
            subnet_cidr_block=cell_cidr_block,
        )

        cell.setup_master(
            name=name,
            key=key,
            count=count,
            image_id=image_id,
            instance_type=instance_type,
            tm_release=tm_release,
            ldap_hostname=ldap_hostname,
            app_root=app_root,
            subnet_cidr_block=cell_cidr_block,
        )

        _ldap = ldap.LDAP(
            name='TreadmillLDAP',
            vpc_id=vpc_id,
            domain=domain
        )

        _ldap.setup(
            key=key,
            count=1,
            image_id=image_id,
            instance_type=instance_type,
            tm_release=tm_release,
            app_root=app_root,
            ldap_hostname=ldap_hostname,
            cidr_block=ldap_cidr_block,
            subnet_id=ldap_subnet_id
        )

        click.echo(
            pprint({
                'Cell': cell.show(),
                'Ldap': _ldap.subnet.show()
            })
        )

    @cloud.command(name='init-domain')
    @click.option('--name', default='TreadmillIPA',
                  help='Name of the instance')
    @click.option('--vpc-id', required=True, help='VPC ID of cell')
    @click.option('--domain', required=True,
                  default=constants.DEFAULT_DOMAIN,
                  help='Domain for hosted zone')
    @click.option('--subnet-cidr-block', help='Cidr block of subnet for IPA',
                  default='172.23.0.0/24')
    @click.option('--subnet-id', help='Subnet ID')
    @click.option('--count', help='Count of the instances', default=1)
    @click.option('--ipa-admin-password', required=True,
                  help='Password for IPA admin')
    @click.option('--tm-release', default='0.1.0', help='Treadmill Release')
    @click.option('--key', required=True, help='SSH key name')
    @click.option('--instance-type',
                  default=constants.INSTANCE_TYPES['EC2']['micro'],
                  help='Instance type')
    @click.option('--image-id', required=True,
                  help='AMI ID to use for new master instance')
    def init_domain(name, vpc_id, domain, subnet_cidr_block, subnet_id, count,
                    ipa_admin_password, tm_release, key,
                    instance_type, image_id):
        """Initialize treadmill domain"""
        ipa = IPA(name=name, vpc_id=vpc_id, domain=domain)
        ipa.setup(
            subnet_id=subnet_id,
            count=count,
            ipa_admin_password=ipa_admin_password,
            tm_release=tm_release,
            key=key,
            instance_type=instance_type,
            image_id=image_id,
            cidr_block=subnet_cidr_block,
        )

        click.echo(
            pprint(ipa.show())
        )

    @cloud.group()
    def delete():
        """Delete Treadmill EC2 Objects"""
        pass

    @delete.command(name='vpc')
    @click.option('--vpc-id', required=True, help='VPC ID of cell')
    @click.option('--domain', required=True,
                  default=constants.DEFAULT_DOMAIN,
                  help='Domain for hosted zone')
    def delete_vpc(vpc_id, domain):
        """Delete VPC"""
        vpc.VPC(id=vpc_id, domain=domain).delete()

    @delete.command(name='cell')
    @click.option('--vpc-id', required=True, help='VPC ID of cell')
    @click.option('--domain', required=True, default=constants.DEFAULT_DOMAIN,
                  help='Domain for hosted zone')
    @click.option('--subnet-id', required=True, help='Subnet ID of cell')
    def delete_cell(vpc_id, domain, subnet_id):
        """Delete Cell (Subnet)"""
        _vpc = vpc.VPC(id=vpc_id, domain=domain)
        _vpc.load_hosted_zone_ids()
        subnet.Subnet(id=subnet_id).destroy(
            hosted_zone_id=_vpc.hosted_zone_id,
            reverse_hosted_zone_id=_vpc.reverse_hosted_zone_id,
            domain=_vpc.domain
        )

    @delete.command(name='domain')
    @click.option('--vpc-id', required=True, help='VPC ID of cell')
    @click.option('--domain', required=True, default=constants.DEFAULT_DOMAIN,
                  help='Domain for hosted zone')
    @click.option('--subnet-id', required=True, help='Subnet ID of IPA')
    @click.option('--name', required=False, help='Name of Instance',
                  default="TreadmillIPA")
    def delete_domain(vpc_id, domain, subnet_id, name):
        """Delete Subnet"""
        ipa = IPA(name=name, vpc_id=vpc_id, domain=domain)
        ipa.destroy(subnet_id=subnet_id)

    @cloud.group()
    def list():
        """Show Treadmill Cloud Resources"""
        pass

    @list.command(name='vpc')
    @click.option('--vpc-id', required=True, help='VPC ID of cell')
    @click.option('--domain', required=True, default=constants.DEFAULT_DOMAIN,
                  help='Domain for hosted zone')
    def vpc_resources(vpc_id, domain):
        """Show VPC"""
        click.echo(
            pprint(vpc.VPC(id=vpc_id, domain=domain).show())
        )

    @list.command(name='cell')
    @click.option('--subnet-id', required=True, help='Subnet ID of cell')
    def cell_resources(subnet_id):
        """Show Cell"""
        click.echo(
            pprint(subnet.Subnet(id=subnet_id).show())
        )

    return cloud
