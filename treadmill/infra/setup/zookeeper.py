from treadmill.infra.setup import base_provision
from treadmill.infra import configuration, constants


class Zookeeper(base_provision.BaseProvision):
    def __init__(self, name, vpc_id):
        super(Zookeeper, self).__init__(
            name=name,
            vpc_id=vpc_id,
        )
        self.subnet_name = constants.TREADMILL_CELL_SUBNET_NAME

    def setup(self, image_id, key, cidr_block, instance_type, subnet_id=None):
        self.configuration = configuration.Zookeeper(
            self.name
        )
        super(Zookeeper, self).setup(
            image_id=image_id,
            count=3,
            cidr_block=cidr_block,
            subnet_id=subnet_id,
            key=key,
            instance_type=instance_type
        )
