from treadmill.infra import ec2object
from treadmill.infra import connection
from treadmill.infra import constants
from treadmill.infra import instances


class Subnet(ec2object.EC2Object):
    def __init__(self, name=None, id=None, metadata=None,
                 vpc_id=None, instances=None):
        super(Subnet, self).__init__(
            name=name,
            id=id,
            metadata=metadata
        )
        self.vpc_id = vpc_id
        self.instances = instances

    @classmethod
    def create(cls, cidr_block, vpc_id, name, gateway_id):
        _ec2_conn = connection.Connection()
        response = _ec2_conn.create_subnet(
            VpcId=vpc_id,
            CidrBlock=cidr_block,
            AvailabilityZone=Subnet._availability_zone()
        )
        _subnet = Subnet(
            id=response['Subnet']['SubnetId'],
            name=name,
            metadata=response,
            vpc_id=vpc_id
        )
        _subnet.create_tags()
        _subnet._create_route_table(gateway_id)
        return _subnet

    def get_route_related_ids(self):
        response = self.ec2_conn.describe_route_tables(
            Filters=self._association_filters()
        )
        self.association_id = self._get_ids_from_associations(
            response['RouteTables'],
            'RouteTableAssociationId'
        )[0]
        self.route_table_id = self._get_ids_from_associations(
            response['RouteTables'],
            'RouteTableId'
        )[0]
        self.id = self._get_ids_from_associations(
            response['RouteTables'],
            'SubnetId')[0]

    def destroy(self, hosted_zone_id,
                reverse_hosted_zone_id, domain):
        self.terminate_instances(hosted_zone_id,
                                 reverse_hosted_zone_id, domain)
        self.get_route_related_ids()
        self.ec2_conn.disassociate_route_table(
            AssociationId=self.association_id
        )
        self.ec2_conn.delete_route_table(
            RouteTableId=self.route_table_id
        )
        self.ec2_conn.delete_subnet(
            SubnetId=self.id
        )

    def get_instances(self, refresh=False):
        if refresh or not self.instances:
            self.instances = instances.Instances.get(
                filters=self._network_filters()
            )

    def terminate_instances(self, hosted_zone_id,
                            reverse_hosted_zone_id, domain):
        if not self.instances:
            self.get_instances()

        if self.instances:
            self.instances.terminate(
                hosted_zone_id=hosted_zone_id,
                reverse_hosted_zone_id=reverse_hosted_zone_id,
                domain=domain
            )

    def refresh(self):
        self.metadata = self.ec2_conn.describe_subnets(
            SubnetIds=[self.id]
        )['Subnets'][0]
        self.vpc_id = self.metadata.get('VpcId', None)

    def show(self):
        self.refresh()
        self.get_instances(refresh=True)
        _instance_details = None
        if self.instances:
            _instance_details = list(map(
                self._instance_details,
                [i.metadata for i in self.instances.instances])
            )

        return {
            'VpcId': self.vpc_id,
            'SubnetId': self.id,
            'Instances': _instance_details
        }

    def _create_route_table(self, gateway_id):
        route_table = self.ec2_conn.create_route_table(VpcId=self.vpc_id)
        self.route_table_id = route_table['RouteTable']['RouteTableId']
        self.ec2_conn.create_route(
            RouteTableId=self.route_table_id,
            DestinationCidrBlock=constants.DESTINATION_CIDR_BLOCK,
            GatewayId=gateway_id
        )
        self.ec2_conn.associate_route_table(
            SubnetId=self.id,
            RouteTableId=self.route_table_id
        )

    def _instance_details(self, data):
        return {
            'Name': self._select_from_tags(data['Tags'], 'Name'),
            'InstanceId': data['InstanceId'],
            'InstanceState': data['State']['Name'],
            'SecurityGroups': data['SecurityGroups'],
            'SubnetId': data['SubnetId']
        }

    def _select_from_tags(self, tags, selector):
        for t in tags:
            if t['Key'] == selector:
                return t['Value']

    @classmethod
    def _availability_zone(cls):
        _map = {
            "us-east-1": "us-east-1a",
            "us-east-2": "us-east-2a",
            "ap-southeast-1": "ap-southeast-1a",
            "ap-southeast-2": "ap-southeast-2a",
            "us-west-1": "us-west-1b",
            "us-west-2": "us-west-2a"
        }

        return _map.get(connection.Connection.region_name, None)

    def _association_filters(self):
        return [{
            'Name': 'association.subnet-id',
            'Values': [self.id]
        }]

    def _network_filters(self):
        return [{
            'Name': 'network-interface.subnet-id',
            'Values': [self.id]
        }]

    def _get_ids_from_associations(self, routes, key):
        return [
            _f.get(key) for _f in sum([_r['Associations'] for _r in routes],
                                      []) if _f.get(key) and not _f.get('Main')
        ]
