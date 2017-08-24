from treadmill.infra import instances
from treadmill.infra import connection
from treadmill.infra import vpc
from treadmill.infra import subnet
from treadmill.infra import constants


class BaseProvision:
    def __init__(
            self,
            name,
            vpc_id
    ):
        self.name = name
        self.vpc = vpc.VPC(id=vpc_id)
        self.route_53_conn = connection.Connection(constants.ROUTE_53)
        self.instances = None
        _role = constants.ROLES.get(
            self.__class__.__name__.upper(),
            'DEFAULT'
        )
        self.role = _role

    def setup(
            self,
            image,
            count,
            key,
            instance_type,
            subnet_id=None,
            cidr_block=None,
    ):
        if not subnet_id and not cidr_block:
            raise Exception(
                'Subnet CIDR block required for creating new subnet'
            )

        self.vpc.load_hosted_zone_ids()
        self.vpc.load_internet_gateway_ids()
        self.vpc.load_security_group_ids()

        if not getattr(self, 'subnet_name', None):
            self.subnet_name = self.name
        if not subnet_id:
            self.vpc.create_subnet(
                cidr_block=cidr_block,
                name=self.subnet_name,
                gateway_id=self.vpc.gateway_ids[0]
            )
            self.subnet = self.vpc.subnets[-1]
        else:
            self.subnet = subnet.Subnet(
                id=subnet_id,
                vpc_id=self.vpc.id
            )

        user_data = ''
        if getattr(self, 'configuration', None):
            self.configuration.cell = self.subnet.id
            user_data = self.configuration.get_userdata()

        self.subnet.instances = instances.Instances.create(
            name=self.name,
            image=image,
            count=count,
            subnet_id=self.subnet.id,
            instance_type=instance_type,
            key_name=key,
            secgroup_ids=self.vpc.secgroup_ids,
            user_data=user_data,
            hosted_zone_id=self.vpc.hosted_zone_id,
            reverse_hosted_zone_id=self.vpc.reverse_hosted_zone_id,
            role=self.role
        )

    def destroy(self, subnet_id):
        self.vpc.load_hosted_zone_ids()
        self.subnet = subnet.Subnet(id=subnet_id)
        self.subnet.destroy(
            hosted_zone_id=self.vpc.hosted_zone_id,
            reverse_hosted_zone_id=self.vpc.reverse_hosted_zone_id,
            role=self.role
        )

    def show(self):
        return self.subnet.show()
