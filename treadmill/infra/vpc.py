from treadmill.infra import connection, constants
from treadmill.infra import subnet, ec2object, instances

import logging

_LOGGER = logging.getLogger(__name__)


class VPC(ec2object.EC2Object):
    def __init__(self, id=None, metadata=None, name=None):
        super().__init__(
            id=id,
            name=name,
            metadata=metadata,
        )
        self.instances = []
        self.secgroup_ids = []
        self.subnet_ids = []
        self.route_table_ids = []
        self.route_related_ids = []
        self.gateway_ids = []
        self.subnets = []
        self.association_ids = []

    def refresh(self):
        self._load()
        self.get_instances()
        self.load_security_group_ids()

    def _load(self):
        self.metadata, = self.ec2_conn.describe_vpcs(
            VpcIds=[self.id]
        )['Vpcs']

    @property
    def cidr_block(self):
        if self.metadata:
            return self.metadata.get('CidrBlock', None)

    @classmethod
    def get_id_from_name(cls, name):
        vpcs = cls.ec2_conn.describe_vpcs(
            Filters=[{
                'Name': 'tag:Name',
                'Values': [name]
            }]
        )['Vpcs']

        if len(vpcs) > 1:
            raise ValueError("Multiple VPCs with name: " + name)
        elif vpcs:
            return vpcs[0]['VpcId']

    @classmethod
    def create(cls, name, cidr_block):
        _vpc = VPC(name=name)
        _vpc.metadata = cls.ec2_conn.create_vpc(CidrBlock=cidr_block)['Vpc']
        _vpc.ec2_conn.modify_vpc_attribute(VpcId=_vpc.id,
                                           EnableDnsHostnames={
                                               'Value': True
                                           })
        if _vpc.name:
            _vpc.create_tags()

        return _vpc

    @classmethod
    def all(cls):
        _vpcs = cls.ec2_conn.describe_vpcs(
            VpcIds=[]
        )['Vpcs']

        return [
            VPC(
                metadata=_vpc,
                id=_vpc['VpcId']
            ) for _vpc in _vpcs]

    @classmethod
    def setup(
            cls,
            cidr_block,
            name=None
    ):
        _vpc = VPC.create(name=name, cidr_block=cidr_block)
        _vpc.create_internet_gateway()
        secgroup_id = _vpc.create_security_group(
            constants.COMMON_SEC_GRP, 'Treadmill Security Group'
        )
        ip_permissions = [{
            'IpProtocol': '-1',
            'UserIdGroupPairs': [{'GroupId': secgroup_id}]
        }]

        _vpc.add_secgrp_rules(ip_permissions, secgroup_id)
        return _vpc

    def create_subnet(self, cidr_block, name, gateway_id):
        self.subnets.append(
            subnet.Subnet.create(
                cidr_block=cidr_block,
                name=name,
                vpc_id=self.id,
                gateway_id=gateway_id
            )
        )

    def create_internet_gateway(self):
        gateway = self.ec2_conn.create_internet_gateway()
        gateway_id = gateway['InternetGateway']['InternetGatewayId']
        self.gateway_ids.append(gateway_id)
        self.ec2_conn.attach_internet_gateway(
            InternetGatewayId=gateway_id,
            VpcId=self.id
        )
        return gateway_id

    def create_security_group(self, group_name, description):
        secgroup_id = self.ec2_conn.create_security_group(
            VpcId=self.id,
            GroupName=group_name,
            Description=description
        )['GroupId']
        self.secgroup_ids.append(secgroup_id)
        return secgroup_id

    def add_secgrp_rules(self, ip_permissions, secgroup_id):
        self.ec2_conn.authorize_security_group_ingress(
            GroupId=secgroup_id,
            IpPermissions=ip_permissions)

    def get_instances(self, refresh=False):
        if refresh or not self.instances:
            self.instances = instances.Instances.get(
                filters=self._filters()
            )

    def terminate_instances(self):
        if not self.instances:
            self.get_instances()

        self.instances.terminate()

    def load_security_group_ids(self, sg_names=None):
        res = self.ec2_conn.describe_security_groups(Filters=self._filters())
        sec_groups = [sg for sg in res['SecurityGroups']]
        if sg_names:
            self.secgroup_ids = [
                sg['GroupId'] for sg in sec_groups
                if sg['GroupName'] in sg_names
            ]
        else:
            self.secgroup_ids = [
                sg['GroupId'] for sg in sec_groups
                if sg['GroupName'] != 'default'
            ]

    def delete_security_groups(self, sg_names=None):
        self.load_security_group_ids(sg_names=sg_names)

        for secgroup_id in self.secgroup_ids:
            self.ec2_conn.delete_security_group(GroupId=secgroup_id)

    def load_route_related_ids(self):
        response = self.ec2_conn.describe_route_tables(Filters=self._filters())
        if not self.association_ids:
            self.association_ids = self._get_ids_from_associations(
                response['RouteTables'],
                'RouteTableAssociationId'
            )
        if not self.route_table_ids:
            self.route_table_ids = [
                route['RouteTableId'] for route in response['RouteTables']
            ]
        if not self.subnet_ids:
            self.subnet_ids = self._get_ids_from_associations(
                response['RouteTables'],
                'SubnetId')

    def delete_route_tables(self):
        if not self.route_related_ids:
            self.load_route_related_ids()

        for ass_id in self.association_ids:
            self.ec2_conn.disassociate_route_table(
                AssociationId=ass_id
            )
        for route_table_id in self.route_table_ids:
            try:
                self.ec2_conn.delete_route_table(
                    RouteTableId=route_table_id
                )
            except Exception as ex:
                _LOGGER.info(ex)
        for subnet_id in self.subnet_ids:
            self.ec2_conn.delete_subnet(
                SubnetId=subnet_id
            )

    def load_internet_gateway_ids(self):
        if not self.gateway_ids:
            response = self.ec2_conn.describe_internet_gateways(
                Filters=[{
                    'Name': constants.ATTACHMENT_VPC_ID,
                    'Values': [self.id],
                }]
            )

            self.gateway_ids = [gw['InternetGatewayId']
                                for gw in response['InternetGateways']]

    def delete_internet_gateway(self):
        self.load_internet_gateway_ids()

        for gateway_id in self.gateway_ids:
            self.ec2_conn.detach_internet_gateway(
                VpcId=self.id,
                InternetGatewayId=gateway_id
            )
            self.ec2_conn.delete_internet_gateway(
                InternetGatewayId=gateway_id
            )

    def delete_dhcp_options(self):
        if self.metadata['DhcpOptionsId'] == 'default':
            return
        self.ec2_conn.delete_dhcp_options(
            DhcpOptionsId=self.metadata['DhcpOptionsId']
        )

    def delete(self):
        self.terminate_instances()
        self.delete_internet_gateway()
        self.delete_security_groups()
        self.delete_route_tables()

        if not self.metadata:
            self._load()

        self.ec2_conn.delete_vpc(VpcId=self.id)
        self.delete_dhcp_options()

    def show(self):
        self._load()
        self.get_instances(refresh=True)
        self.load_route_related_ids()
        return {
            'VpcId': self.id,
            'Name': self.name,
            'Subnets': self.subnet_ids,
            'Instances': list(map(
                self._instance_details,
                self.instances.instances)
            )
        }

    def _create_dhcp_options(self, options=None):
        _default_options = [
            {
                'Key': 'domain-name',
                'Values': [connection.Connection.context.domain]
            }
        ]
        response = self.ec2_conn.create_dhcp_options(
            DhcpConfigurations=_default_options + (options or [])
        )

        return response['DhcpOptions']['DhcpOptionsId']

    def associate_dhcp_options(self, options=None, default=False):
        if default:
            self.dhcp_options_id = 'default'
        else:
            self.dhcp_options_id = self._create_dhcp_options(options)

        self.ec2_conn.associate_dhcp_options(
            DhcpOptionsId=self.dhcp_options_id,
            VpcId=self.id
        )

    def list_cells(self):
        subnets = self.ec2_conn.describe_subnets(
            Filters=[
                {
                    'Name': 'vpc-id',
                    'Values': [self.id]
                }
            ]
        )['Subnets']
        return [s['SubnetId'] for s in subnets]

    def reverse_domain_name(self):
        if not self.cidr_block:
            self._load()
        cidr_block_octets = self.cidr_block.split('.')
        return '.'.join([
            cidr_block_octets[1],
            cidr_block_octets[0],
            constants.REVERSE_DNS_TLD
        ])

    def _instance_details(self, instance):
        return {
            'Name': instance.name,
            'Role': instance.role,
            'HostName': instance.hostname,
            'InstanceId': instance.id,
            'InstanceState': instance.metadata['State']['Name'],
            'SecurityGroups': instance.metadata['SecurityGroups'],
            'SubnetId': instance.metadata['SubnetId'],
            'PublicIpAddress': instance.metadata.get('PublicIpAddress', None),
            'PrivateIpAddress': instance.metadata.get(
                'PrivateIpAddress', None
            ),
            'InstanceType': instance.metadata.get('InstanceType', None),
        }

    def _select_from_tags(self, tags, selector):
        for t in tags:
            if t['Key'] == selector:
                return t['Value']

    def _get_ids_from_associations(self, routes, key):
        return [
            _f.get(key) for _f in sum([_r['Associations'] for _r in routes],
                                      []) if _f.get(key) and not _f.get('Main')
        ]

    def _filters(self):
        return [{
            'Name': 'vpc-id',
            'Values': [self.id]
        }]
