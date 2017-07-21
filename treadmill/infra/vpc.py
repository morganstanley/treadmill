from treadmill.infra import connection
from treadmill.infra import instances
from treadmill.infra import constants
from treadmill.infra import subnet

import time
import logging

_LOGGER = logging.getLogger(__name__)


class VPC:
    def __init__(self, id=None, metadata=None):
        self.ec2_conn = connection.Connection()
        self.route53_conn = connection.Connection(resource=constants.ROUTE_53)
        self.id = id
        self.metadata = metadata
        self.cidr_block = None
        self.instances = []
        self.secgroup_ids = []
        self.subnet_ids = []
        self.route_table_ids = []
        self.route_related_ids = []
        self.gateway_ids = []
        self.subnets = []
        self.association_ids = []
        self.hosted_zone_id = None
        self.reverse_hosted_zone_id = None
        self.hosted_zone_ids = set()

    def refresh(self):
        self._load()
        self.get_instances()
        self.load_hosted_zone_ids()
        self.load_security_group_ids()

    def _load(self):
        self.metadata, = self.ec2_conn.describe_vpcs(
            VpcIds=[self.id]
        )['Vpcs']
        self.cidr_block = self.metadata['CidrBlock']

    def create(self, cidr_block):
        self.metadata = self.ec2_conn.create_vpc(CidrBlock=cidr_block)['Vpc']
        self.cidr_block = self.metadata['CidrBlock']
        self.id = self.metadata['VpcId']
        self.ec2_conn.create_tags(
            Resources=[self.id],
            Tags=[{
                'Key': 'Name',
                'Value': 'Treadmill-vpc'
            }]
        )
        self.ec2_conn.modify_vpc_attribute(VpcId=self.id,
                                           EnableDnsHostnames={
                                               'Value': True
                                           })

    @classmethod
    def setup(
            cls,
            cidr_block,
            secgroup_name,
            secgroup_desc,
    ):
        _vpc = VPC()
        _vpc.create(cidr_block=cidr_block)
        _vpc.create_internet_gateway()
        _vpc.create_security_group(secgroup_name, secgroup_desc)
        _vpc.create_hosted_zone()
        _vpc.create_hosted_zone(reverse=True)
        _vpc.associate_dhcp_options()

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
        _ALL = '-1'
        secgroup_id = self.ec2_conn.create_security_group(
            VpcId=self.id,
            GroupName=group_name,
            Description=description
        )['GroupId']
        self.secgroup_ids.append(secgroup_id)

        self.ec2_conn.authorize_security_group_ingress(
            GroupId=secgroup_id,
            IpPermissions=[{
                'IpProtocol': _ALL,
                'UserIdGroupPairs': [{'GroupId': secgroup_id}]
            }]
        )

    def create_hosted_zone(self, reverse=False):
        if reverse:
            identifier = 'reverse_hosted_zone_id'
            name = self._reverse_domain_name()
        else:
            identifier = 'hosted_zone_id'
            name = connection.Connection.context.domain

        if not getattr(self, identifier):
            _hosted_zone_id = self.route53_conn.create_hosted_zone(
                Name=name,
                VPC={
                    'VPCRegion': connection.Connection.context.region_name,
                    'VPCId': self.id,
                },
                HostedZoneConfig={
                    'PrivateZone': True
                },
                CallerReference=str(int(time.time()))
            )['HostedZone']['Id']
            setattr(self, identifier, _hosted_zone_id)

    def load_hosted_zone_ids(self):
        forward_hosted_zones = self.route53_conn.list_hosted_zones_by_name(
            DNSName=connection.Connection.context.domain
        )['HostedZones']
        reverse_hosted_zones = self.route53_conn.list_hosted_zones_by_name(
            DNSName=self._reverse_domain_name()
        )['HostedZones']

        hosted_zones = forward_hosted_zones + reverse_hosted_zones

        for hosted_zone in hosted_zones:
            _hosted_zone_id = hosted_zone['Id']
            hosted_zone_details = self.route53_conn.get_hosted_zone(
                Id=_hosted_zone_id
            )
            if self.id in [_vpc['VPCId']
                           for _vpc in hosted_zone_details['VPCs']]:
                if 'in-addr.arpa' in hosted_zone_details['HostedZone']['Name']:
                    self.reverse_hosted_zone_id = _hosted_zone_id
                else:
                    self.hosted_zone_id = _hosted_zone_id
                self.hosted_zone_ids.add(_hosted_zone_id)

        self.hosted_zone_ids = list(self.hosted_zone_ids)

    def delete_hosted_zones(self):
        if not self.hosted_zone_ids:
            self.load_hosted_zone_ids()

        for id in self.hosted_zone_ids:
            self.route53_conn.delete_hosted_zone(
                Id=id
            )

    def get_instances(self, refresh=False):
        if refresh or not self.instances:
            self.instances = instances.Instances.get(
                filters=self._filters()
            )

    def terminate_instances(self):
        if not self.instances:
            self.get_instances()
        if not self.hosted_zone_ids:
            self.load_hosted_zone_ids()

        self.instances.terminate(
            hosted_zone_id=self.hosted_zone_id,
            reverse_hosted_zone_id=self.reverse_hosted_zone_id,
        )

    def load_security_group_ids(self):
        if not self.secgroup_ids:
            res = self.ec2_conn.describe_security_groups(
                Filters=self._filters()
            )
            self.secgroup_ids = [sg['GroupId'] for sg in res['SecurityGroups']
                                 if sg['GroupName'] != 'default']

    def delete_security_groups(self):
        self.load_security_group_ids()

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

    def delete(self):
        self.terminate_instances()
        self.delete_internet_gateway()
        self.delete_security_groups()
        self.delete_route_tables()
        self.delete_hosted_zones()
        self.ec2_conn.delete_vpc(VpcId=self.id)

    def show(self):
        self.get_instances(refresh=True)
        self.load_route_related_ids()
        return {
            'VpcId': self.id,
            'Subnets': self.subnet_ids,
            'Instances': list(map(
                self._instance_details,
                self.instances.instances)
            )
        }

    def associate_dhcp_options(self, options=[]):
        _default_options = [
            {
                'Key': 'domain-name',
                'Values': [connection.Connection.context.domain]
            },
            {
                'Key': 'domain-name-servers',
                'Values': ['AmazonProvidedDNS']
            }
        ]
        response = self.ec2_conn.create_dhcp_options(
            DhcpConfigurations=_default_options + options
        )

        self.dhcp_options_id = response['DhcpOptions']['DhcpOptionsId']
        self.ec2_conn.associate_dhcp_options(
            DhcpOptionsId=self.dhcp_options_id,
            VpcId=self.id
        )

    def _reverse_domain_name(self):
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
