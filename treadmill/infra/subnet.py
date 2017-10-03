from treadmill.infra import ec2object
from treadmill.infra import connection
from treadmill.infra import constants
from treadmill.infra import instances

import logging

_LOGGER = logging.getLogger(__name__)


class Subnet(ec2object.EC2Object):
    def __init__(self, name=None, id=None, metadata=None,
                 vpc_id=None, instances=None):
        super().__init__(
            name=name,
            id=id,
            metadata=metadata
        )
        self.vpc_id = vpc_id
        self.instances = instances

    @classmethod
    def _load_json(cls, vpc_id, name, restrict_one=True):
        _ec2_conn = connection.Connection()
        _json = _ec2_conn.describe_subnets(
            Filters=[
                {
                    'Name': 'vpc-id',
                    'Values': [vpc_id]
                },
                {
                    'Name': 'tag:Name',
                    'Values': [name]
                }
            ]
        )['Subnets']

        if restrict_one:
            if len(_json) > 1:
                raise ValueError("Multiple Subnets with name: " + name)
            elif _json:
                return _json[0]
        else:
            return _json

    @classmethod
    def get(cls, vpc_id, name, restrict_one=True):
        _metadata = cls._load_json(
            vpc_id=vpc_id,
            name=name,
            restrict_one=restrict_one
        )

        return Subnet(
            metadata=_metadata,
            vpc_id=vpc_id,
        )

    @classmethod
    def create(cls, cidr_block, vpc_id, name, gateway_id):
        metadata = cls._create(cidr_block, vpc_id, name, gateway_id)
        _subnet = Subnet(
            name=name,
            metadata=metadata,
            vpc_id=vpc_id
        )
        _subnet.create_tags()
        _subnet._create_route_table(gateway_id)
        return _subnet

    @classmethod
    def _create(cls, cidr_block, vpc_id, name, gateway_id):
        _ec2_conn = connection.Connection()
        return _ec2_conn.create_subnet(
            VpcId=vpc_id,
            CidrBlock=cidr_block,
            AvailabilityZone=Subnet._availability_zone()
        )['Subnet']

    @property
    def persisted(self):
        return True if (
            self.metadata and self.metadata.get('SubnetId')
        ) else False

    def persist(self, cidr_block, gateway_id):
        self.metadata = Subnet._create(
            cidr_block=cidr_block,
            gateway_id=gateway_id,
            name=self.name,
            vpc_id=self.vpc_id
        )
        self.create_tags()
        self._create_route_table(gateway_id)

    def load_route_related_ids(self):
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

    def destroy(self, role=None):
        self.refresh()
        self.terminate_instances(role)

        remaining_instances = self._get_instances_by_filters(
            filters=self._network_filters()
        ).instances

        if not remaining_instances:
            self.load_route_related_ids()
            self.ec2_conn.disassociate_route_table(
                AssociationId=self.association_id
            )
            self.ec2_conn.delete_route_table(
                RouteTableId=self.route_table_id
            )
            self.ec2_conn.delete_subnet(
                SubnetId=self.id
            )
        else:
            _LOGGER.info('keeping the subnet as other instances are alive.')
            return

    def get_instances(self, refresh=False, role=None):
        if role:
            self.get_instances_by_role(refresh=refresh, role=role)
        else:
            self.get_all_instances(refresh=refresh)

    def get_all_instances(self, refresh=False):
        if refresh or not self.instances:
            self.instances = self._get_instances_by_filters(
                filters=self._network_filters()
            )

    def _get_instances_by_filters(self, filters):
        return instances.Instances.get(
            filters=filters
        )

    def get_instances_by_role(self, role, refresh=False):
        if refresh or not self.instances:
            self.instances = self._get_instances_by_filters(
                filters=self._network_filters(
                    extra_filters=self._role_filter(role)
                )
            )

    def terminate_instances(self, role):
        if not self.instances:
            self.get_instances(refresh=True, role=role)

        self.instances.terminate()

    def refresh(self):
        if self.id:
            self.metadata = self.ec2_conn.describe_subnets(
                SubnetIds=[self.id]
            )['Subnets'][0]
            self.vpc_id = self.metadata.get('VpcId', None)
        else:
            self.metadata = Subnet._load_json(
                name=self.name,
                vpc_id=self.vpc_id
            )

    def show(self, role=None):
        self.refresh()
        self.get_instances(refresh=True, role=role)
        _instance_details = None
        if self.instances:
            _instance_details = list(map(
                self._instance_details,
                self.instances.instances)
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

        return _map.get(connection.Connection.context.region_name, None)

    def _role_filter(self, role):
        return [
            {
                'Name': 'tag-key',
                'Values': ['Role']
            },
            {
                'Name': 'tag-value',
                'Values': [role]
            }
        ]

    def _association_filters(self):
        return [{
            'Name': 'association.subnet-id',
            'Values': [self.id]
        }]

    def _network_filters(self, extra_filters=None):
        default_filters = [{
            'Name': 'network-interface.subnet-id',
            'Values': [self.id]
        }]

        if extra_filters:
            return default_filters + extra_filters
        else:
            return default_filters

    def _get_ids_from_associations(self, routes, key):
        return [
            _f.get(key) for _f in sum([_r['Associations'] for _r in routes],
                                      []) if _f.get(key) and not _f.get('Main')
        ]
