"""
Unit test for VPC.
"""

import unittest
import mock
from treadmill.infra import vpc


class VPCTest(unittest.TestCase):
    """Tests supervisor routines."""

    def setUp(self):
        self.vpc_id_mock = '786'
        self.subnet_id_mock = '111'
        self.gateway_id_mock = '007'
        self.route_table_id_mock = '411'
        self.security_group_id_mock = '777'
        self.internet_gateway_id_mock = '999'

    @mock.patch('treadmill.infra.connection.Connection',
                mock.Mock(return_value='foo'))
    def test_init(self):
        _vpc = vpc.VPC()

        self.assertEquals(_vpc.ec2_conn, 'foo')
        self.assertIsNone(_vpc.id)

    @mock.patch('treadmill.infra.connection.Connection')
    def test_create(self, connectionMock):
        _connectionMock = connectionMock()
        vpc_response_mock = {
            'Vpc': {
                'VpcId': self.vpc_id_mock,
                'CidrBlock': '172.16.0.0/16'
            }
        }
        _connectionMock.create_vpc = mock.Mock(return_value=vpc_response_mock)
        _connectionMock.create_tags = mock.Mock()

        _vpc = vpc.VPC()
        _vpc.create(cidr_block='172.16.0.0/16')

        self.assertEquals(_vpc.id, self.vpc_id_mock)
        self.assertEquals(_vpc.metadata, vpc_response_mock['Vpc'])
        self.assertEquals(_vpc.cidr_block, '172.16.0.0/16')
        _connectionMock.create_vpc.assert_called_once_with(
            CidrBlock='172.16.0.0/16'
        )
        _connectionMock.create_tags.assert_called_once_with(
            Resources=[self.vpc_id_mock],
            Tags=[{
                'Key': 'Name',
                'Value': 'Treadmill-vpc'
            }]
        )
        _connectionMock.modify_vpc_attribute.assert_called_once_with(
            VpcId=self.vpc_id_mock,
            EnableDnsHostnames={
                'Value': True
            })

    @mock.patch('treadmill.infra.subnet.Subnet')
    @mock.patch('treadmill.infra.connection.Connection')
    def test_create_subnet(self, ConnectionMock, SubnetMock):
        _vpc = vpc.VPC(id=self.vpc_id_mock)
        _vpc.create_subnet(
            name='subnet-name',
            cidr_block='172.23.0.0/24',
            gateway_id='gateway-id'
        )

        SubnetMock.create.assert_called_once_with(
            name='subnet-name',
            vpc_id=self.vpc_id_mock,
            cidr_block='172.23.0.0/24',
            gateway_id='gateway-id'
        )

    @mock.patch('treadmill.infra.connection.Connection')
    def test_create_internet_gateway(self, connectionMock):
        _connectionMock = connectionMock()
        _connectionMock.create_internet_gateway = mock.Mock(return_value={
            'InternetGateway': {
                'InternetGatewayId': self.gateway_id_mock
            }
        })
        _connectionMock.attach_internet_gatway = mock.Mock()

        _vpc = vpc.VPC(id=self.vpc_id_mock)
        _vpc.create_internet_gateway()

        self.assertEquals(_vpc.gateway_ids, [self.gateway_id_mock])
        _connectionMock.create_internet_gateway.assert_called_once()
        _connectionMock.attach_internet_gateway.assert_called_once_with(
            InternetGatewayId=self.gateway_id_mock,
            VpcId=self.vpc_id_mock
        )

    @mock.patch('treadmill.infra.connection.Connection')
    def test_create_security_group(self, connectionMock):
        _connMock = connectionMock()
        _connMock.create_security_group = mock.Mock(return_value={
            'GroupId': self.security_group_id_mock
        })

        _vpc = vpc.VPC(id=self.vpc_id_mock)
        _vpc.create_security_group(
            group_name='foobar',
            description='foobar description'
        )

        self.assertEquals(_vpc.secgroup_ids, [self.security_group_id_mock])
        _connMock.create_security_group.assert_called_once_with(
            GroupName='foobar',
            Description='foobar description',
            VpcId=self.vpc_id_mock
        )

        _connMock.authorize_security_group_ingress.assert_called_once_with(
            GroupId=self.security_group_id_mock,
            IpPermissions=[{
                'IpProtocol': '-1',
                'UserIdGroupPairs': [{'GroupId': self.security_group_id_mock}]
            }]
        )

    @mock.patch('treadmill.infra.connection.Connection')
    @mock.patch('time.time', mock.Mock(return_value=786.007))
    def test_create_hosted_zone(self, connectionMock):
        connectionMock.context.domain = 'foo.bar'
        _connectionMock = connectionMock('route53')
        connectionMock.context.region_name = 'us-east-1'
        expected_hosted_zone = {
            'HostedZone': {
                'Id': 'Some-Zone-Id'
            },
            'VPC': {
                'Id': self.vpc_id_mock
            }
        }
        _connectionMock.create_hosted_zone = mock.Mock(
            return_value=expected_hosted_zone
        )

        _vpc = vpc.VPC(id=self.vpc_id_mock)
        _vpc.create_hosted_zone()

        self.assertEquals(
            _vpc.hosted_zone_id,
            expected_hosted_zone['HostedZone']['Id']
        )
        _connectionMock.create_hosted_zone.assert_called_once_with(
            Name='foo.bar',
            VPC={
                'VPCRegion': 'us-east-1',
                'VPCId': self.vpc_id_mock,
            },
            HostedZoneConfig={
                'PrivateZone': True
            },
            CallerReference='786'
        )

    @mock.patch('treadmill.infra.connection.Connection')
    @mock.patch('time.time', mock.Mock(return_value=786.007))
    def test_create_hosted_zone_reverse(self, connectionMock):
        _connectionMock = connectionMock('route53')
        connectionMock.context.region_name = 'us-east-1'
        expected_hosted_zone = {
            'HostedZone': {
                'Id': 'Some-Zone-Id'
            },
            'VPC': {
                'Id': self.vpc_id_mock
            }
        }
        _connectionMock.create_hosted_zone = mock.Mock(
            return_value=expected_hosted_zone
        )

        _vpc = vpc.VPC(id=self.vpc_id_mock)
        _vpc.cidr_block = '172.10.0.0/16'
        _vpc.create_hosted_zone(reverse=True)

        self.assertEquals(
            _vpc.reverse_hosted_zone_id,
            expected_hosted_zone['HostedZone']['Id']
        )
        _connectionMock.create_hosted_zone.assert_called_once_with(
            Name='10.172.in-addr.arpa',
            VPC={
                'VPCRegion': 'us-east-1',
                'VPCId': self.vpc_id_mock,
            },
            HostedZoneConfig={
                'PrivateZone': True
            },
            CallerReference='786'
        )

    @mock.patch('treadmill.infra.instances.connection.Connection')
    @mock.patch('treadmill.infra.instances.Instances')
    @mock.patch('treadmill.infra.vpc.instances.Instances')
    def test_get_instances(self, connectionMock, instances_mock,
                           vpc_instances_mock):
        instances_mock.get = vpc_instances_mock.get = mock.Mock(
            return_value='foo'
        )
        connectionMock.describe_vpcs = mock.Mock(
            return_value={'Vpcs': [{'VpcId': self.vpc_id_mock, 'foo': 'bar'}]}
        )

        _vpc = vpc.VPC(id=self.vpc_id_mock)
        _vpc.get_instances(refresh=True)

        self.assertEquals(
            _vpc.instances,
            'foo'
        )

        instances_mock.get.assert_called_once_with(
            filters=[{
                'Name': 'vpc-id',
                'Values': [self.vpc_id_mock],
            }]
        )

    @mock.patch('treadmill.infra.instances.connection.Connection')
    @mock.patch('treadmill.infra.instances.Instances')
    @mock.patch('treadmill.infra.vpc.instances.Instances')
    def test_terminate_instances(self, connectionMock, instances_mock,
                                 vpc_instances_mock):
        instances_obj_mock = mock.Mock()
        connectionMock.describe_vpcs = mock.Mock(
            return_value={'Vpcs': [{'VpcId': self.vpc_id_mock, 'foo': 'bar'}]}
        )

        _vpc = vpc.VPC(id=self.vpc_id_mock)
        _vpc.instances = instances_obj_mock
        _vpc.hosted_zone_ids = [1, 2]
        _vpc.hosted_zone_id = 1
        _vpc.reverse_hosted_zone_id = 2

        _vpc.terminate_instances()

        instances_obj_mock.terminate.assert_called_once_with(
            hosted_zone_id=1,
            reverse_hosted_zone_id=2,
        )

    @mock.patch('treadmill.infra.connection.Connection')
    def test_load_security_group_ids(self, connectionMock):
        _connectionMock = connectionMock()
        _connectionMock.describe_security_groups = mock.Mock(return_value={
            'SecurityGroups': [{
                'GroupId': 'secgroup-id-0',
                'GroupName': 'foobar'
            }, {
                'GroupId': 'secgroup-id-1',
                'GroupName': 'default'
            }]
        })

        _vpc = vpc.VPC(id=self.vpc_id_mock)
        _vpc.load_security_group_ids()

        _connectionMock.describe_security_groups.assert_called_once_with(
            Filters=[{
                'Name': 'vpc-id',
                'Values': [self.vpc_id_mock]
            }]
        )

    @mock.patch('treadmill.infra.connection.Connection')
    def test_delete_security_groups(self, connectionMock):
        _connectionMock = connectionMock()
        _connectionMock.delete_security_group = mock.Mock()

        _vpc = vpc.VPC(id=self.vpc_id_mock)
        _vpc.secgroup_ids = ['secgroup-id-0', 'secgroup-id-1']
        _vpc.delete_security_groups()

        self.assertCountEqual(
            _connectionMock.delete_security_group.mock_calls,
            [
                mock.mock.call(GroupId='secgroup-id-0'),
                mock.mock.call(GroupId='secgroup-id-1')
            ]
        )

    @mock.patch('treadmill.infra.connection.Connection')
    def test_load_hosted_zone_ids(self, connectionMock):
        connectionMock.context.domain = 'foo.bar'
        _connectionMock = connectionMock('route53')
        _connectionMockEc2 = connectionMock('ec2')
        _connectionMock.describe_vpcs = mock.Mock(return_value={
            'Vpcs': [{
                'CidrBlock': '172.0.0.1'
            }]
        })
        _connectionMock.list_hosted_zones_by_name.side_effect = [
            {
                'HostedZones': [{
                    'Id': 'zone-id',
                    'Name': 'zone-name',
                }, {
                    'Id': 'zone-id-1',
                    'Name': 'zone-name-foo',
                }]
            }, {
                'HostedZones': [{
                    'Id': 'zone-id-reverse',
                    'Name': 'zone-name.in-addr-arpa',
                }]
            }
        ]
        _connectionMock.get_hosted_zone = mock.Mock()
        _connectionMock.get_hosted_zone.side_effect = [
            {
                'HostedZone': {
                    'Id': 'zone-id',
                    'Name': 'zone-name',
                },
                'VPCs': [{
                    'VPCRegion': 'region',
                    'VPCId': self.vpc_id_mock
                }]
            },
            {
                'HostedZone': {
                    'Id': 'zone-id-1',
                    'Name': 'zone-name-foo',
                },
                'VPCs': [{
                    'VPCRegion': 'region',
                    'VPCId': 'foobar'
                }]
            },
            {
                'HostedZone': {
                    'Id': 'zone-id-reverse',
                    'Name': 'zone-name.in-addr.arpa',
                },
                'VPCs': [{
                    'VPCRegion': 'region',
                    'VPCId': self.vpc_id_mock
                }]
            }
        ]

        _vpc = vpc.VPC(id=self.vpc_id_mock)
        _vpc.load_hosted_zone_ids()

        self.assertCountEqual(
            _vpc.hosted_zone_ids,
            ['zone-id', 'zone-id-reverse']
        )
        self.assertEqual(
            _vpc.hosted_zone_id,
            'zone-id'
        )
        self.assertEqual(
            _vpc.reverse_hosted_zone_id,
            'zone-id-reverse'
        )
        _connectionMockEc2.describe_vpcs.assert_called_once_with(
            VpcIds=[self.vpc_id_mock]
        )
        self.assertCountEqual(
            _connectionMock.list_hosted_zones_by_name.mock_calls,
            [
                mock.mock.call(DNSName='foo.bar'),
                mock.mock.call(DNSName='0.172.in-addr.arpa')
            ]
        )
        self.assertCountEqual(
            _connectionMock.get_hosted_zone.mock_calls,
            [
                mock.mock.call(Id='zone-id'),
                mock.mock.call(Id='zone-id-reverse'),
                mock.mock.call(Id='zone-id-1')
            ]
        )

    @mock.patch('treadmill.infra.connection.Connection')
    def test_delete_hosted_zones(self, connectionMock):
        _connectionMock = connectionMock('route53')
        _connectionMock.delete_hosted_zone = mock.Mock()

        _vpc = vpc.VPC(id=self.vpc_id_mock)
        _vpc.hosted_zone_ids = [1]

        _vpc.delete_hosted_zones()

        _connectionMock.delete_hosted_zone.assert_called_once_with(
            Id=1
        )

    @mock.patch('treadmill.infra.connection.Connection')
    def test_load_route_related_ids(self, connectionMock):
        route_table_response_mock = {
            'RouteTables': [{
                'RouteTableId': 'route_table_id_0',
                'VpcId': self.vpc_id_mock,
                'Routes': [{
                    'GatewayId': 'gateway_id_0',
                    'InstanceId': 'route_instance_id_0',
                }],
                'Associations': [{
                    'RouteTableAssociationId': 'ass_id_0',
                    'RouteTableId': 'route_table_id_0',
                    'SubnetId': 'subnet_id_0',
                }]
            }, {
                'RouteTableId': 'route_table_id_1',
                'VpcId': self.vpc_id_mock,
                'Routes': [{
                    'GatewayId': 'gateway_id_1',
                    'InstanceId': 'route_instance_id_1',
                }],
                'Associations': [{
                    'RouteTableAssociationId': 'ass_id_1',
                    'RouteTableId': 'route_table_id_1',
                    'SubnetId': 'subnet_id_1',
                }]
            }]
        }

        _connectionMock = connectionMock()
        _connectionMock.describe_route_tables = mock.Mock(
            return_value=route_table_response_mock
        )
        _vpc = vpc.VPC(id=self.vpc_id_mock)
        _vpc.load_route_related_ids()
        self.assertEquals(_vpc.association_ids, ['ass_id_0', 'ass_id_1'])
        self.assertEquals(_vpc.route_table_ids,
                          ['route_table_id_0', 'route_table_id_1'])
        self.assertEquals(_vpc.subnet_ids, ['subnet_id_0', 'subnet_id_1'])

        _connectionMock.describe_route_tables.assert_called_once_with(
            Filters=[{
                'Name': 'vpc-id',
                'Values': [self.vpc_id_mock]
            }]
        )

    @mock.patch('treadmill.infra.connection.Connection')
    def test_delete_route_tables(self, connectionMock):
        _connectionMock = connectionMock()
        _connectionMock.disassociate_route_table = mock.Mock()
        _connectionMock.delete_route_table = mock.Mock()
        _connectionMock.delete_subnet = mock.Mock()

        _vpc = vpc.VPC(id=self.vpc_id_mock)
        _vpc.route_related_ids = 'foo'
        _vpc.association_ids = ['ass-id']
        _vpc.route_table_ids = ['route-table-id']
        _vpc.subnet_ids = ['subnet-id']
        _vpc.delete_route_tables()

        _connectionMock.disassociate_route_table.assert_called_once_with(
            AssociationId='ass-id'
        )

        _connectionMock.delete_route_table.assert_called_once_with(
            RouteTableId='route-table-id'
        )

        _connectionMock.delete_subnet.assert_called_once_with(
            SubnetId='subnet-id'
        )

    @mock.patch.object(vpc.VPC, 'delete_hosted_zones')
    @mock.patch.object(vpc.VPC, 'delete_route_tables')
    @mock.patch.object(vpc.VPC, 'delete_security_groups')
    @mock.patch.object(vpc.VPC, 'delete_internet_gateway')
    @mock.patch.object(vpc.VPC, 'terminate_instances')
    @mock.patch('treadmill.infra.connection.Connection')
    def test_delete(
            self,
            connectionMock,
            terminate_instances_mock,
            delete_internet_gateway_mock,
            delete_security_groups_mock,
            delete_route_tables_mock,
            delete_hosted_zones_mock
    ):
        _connectionMock = connectionMock()
        _connectionMock.delete_vpc = mock.Mock()

        _vpc = vpc.VPC(id=self.vpc_id_mock)
        _vpc.delete()

        terminate_instances_mock.assert_called_once()
        delete_internet_gateway_mock.assert_called_once()
        delete_security_groups_mock.assert_called_once()
        delete_route_tables_mock.assert_called_once()
        delete_hosted_zones_mock.assert_called_once()
        _connectionMock.delete_vpc.assert_called_once_with(
            VpcId=self.vpc_id_mock
        )

    @mock.patch('treadmill.infra.connection.Connection')
    def test_get_internet_gateway_id(self, connectionMock):
        _connectionMock = connectionMock()
        _connectionMock.describe_internet_gateways = mock.Mock(return_value={
            'InternetGateways': [
                {
                    'InternetGatewayId': self.internet_gateway_id_mock
                }
            ]
        })

        _vpc = vpc.VPC(id=self.vpc_id_mock)
        _vpc.load_internet_gateway_ids()

        self.assertEquals(_vpc.gateway_ids, [self.internet_gateway_id_mock])

        _connectionMock.describe_internet_gateways.assert_called_once_with(
            Filters=[{
                'Name': 'attachment.vpc-id',
                'Values': [self.vpc_id_mock]
            }]
        )

    @mock.patch('treadmill.infra.connection.Connection')
    def test_delete_internet_gateway(self, connectionMock):
        _connectionMock = connectionMock()
        _connectionMock.delete_internet_gateway = mock.Mock()

        _vpc = vpc.VPC(id=self.vpc_id_mock)
        _vpc.gateway_ids = [self.internet_gateway_id_mock]
        _vpc.delete_internet_gateway()

        _connectionMock.delete_internet_gateway.assert_called_once_with(
            InternetGatewayId=self.internet_gateway_id_mock
        )

    @mock.patch('treadmill.infra.connection.Connection')
    def test_associate_dhcp_options(self, connectionMock):
        connectionMock.context.domain = 'cloud.ms.com'
        _connectionMock = connectionMock()
        _connectionMock.create_dhcp_options = mock.Mock(return_value={
            'DhcpOptions': {
                'DhcpOptionsId': 'some-dhcp-id'
            }
        })
        _connectionMock.associate_dhcp_options = mock.Mock()

        _vpc = vpc.VPC(id=self.vpc_id_mock)
        _vpc.associate_dhcp_options()

        _connectionMock.create_dhcp_options.assert_called_once_with(
            DhcpConfigurations=[
                {
                    'Key': 'domain-name',
                    'Values': ['cloud.ms.com']
                },
                {
                    'Key': 'domain-name-servers',
                    'Values': ['AmazonProvidedDNS']
                }
            ]
        )
        _connectionMock.associate_dhcp_options.assert_called_once_with(
            DhcpOptionsId='some-dhcp-id',
            VpcId=self.vpc_id_mock
        )

    @mock.patch.object(vpc.VPC, 'get_instances')
    @mock.patch.object(vpc.VPC, 'load_hosted_zone_ids')
    @mock.patch.object(vpc.VPC, 'load_security_group_ids')
    @mock.patch('treadmill.infra.connection.Connection')
    def test_refresh(self,
                     connectionMock,
                     security_group_ids_mock,
                     hosted_zone_ids_mock,
                     instances_mock):
        _connectionMock = connectionMock()
        _vpc_metadata_mock = {
            'VpcId': self.vpc_id_mock,
            'CidrBlock': '172.0.0.1'
        }
        _connectionMock.describe_vpcs = mock.Mock(
            return_value={'Vpcs': [_vpc_metadata_mock]}
        )
        _vpc = vpc.VPC(id=self.vpc_id_mock)
        _vpc.refresh()
        self.assertIsInstance(_vpc, vpc.VPC)
        self.assertEqual(_vpc.id, self.vpc_id_mock)
        self.assertEqual(_vpc.metadata, _vpc_metadata_mock)
        self.assertEqual(_vpc.cidr_block, '172.0.0.1')
        _connectionMock.describe_vpcs.assert_called_once_with(
            VpcIds=[self.vpc_id_mock]
        )
        instances_mock.assert_called_once()
        hosted_zone_ids_mock.assert_called_once()
        security_group_ids_mock.assert_called_once()

    @mock.patch.object(vpc.VPC, 'associate_dhcp_options')
    @mock.patch.object(vpc.VPC, 'create_hosted_zone')
    @mock.patch.object(vpc.VPC, 'create_security_group')
    @mock.patch.object(vpc.VPC, 'create_internet_gateway')
    @mock.patch.object(vpc.VPC, 'create')
    @mock.patch('treadmill.infra.connection.Connection')
    def test_setup(
            self,
            connectionMock,
            create_mock,
            create_internet_gateway_mock,
            create_security_group_mock,
            create_hosted_zone_mock,
            associate_dhcp_options_mock
    ):
        _vpc = vpc.VPC.setup(
            cidr_block='172.23.0.0/24',
            secgroup_name='secgroup_name',
            secgroup_desc='secgroup_desc',
        )

        self.assertIsInstance(_vpc, vpc.VPC)
        create_mock.assert_called_once_with(
            cidr_block='172.23.0.0/24'
        )
        create_internet_gateway_mock.assert_called_once()
        create_security_group_mock.assert_called_once()
        self.assertCountEqual(
            create_hosted_zone_mock.mock_calls,
            [
                mock.mock.call(),
                mock.mock.call(reverse=True)
            ]
        )
        associate_dhcp_options_mock.assert_called_once()


if __name__ == '__main__':
    unittest.main()
