import logging

from treadmill.infra import vpc, subnet
from treadmill.infra.setup import master, zookeeper

_LOGGER = logging.getLogger(__name__)


class Cell:
    def __init__(self, subnet_name, vpc_id):
        self.subnet_name = subnet_name
        self.vpc = vpc.VPC(id=vpc_id)

    def setup_zookeeper(self, name, key, image, instance_type,
                        subnet_cidr_block, ipa_admin_password, count,
                        proid):
        self.zookeeper = zookeeper.Zookeeper(name=name, vpc_id=self.vpc.id)
        self.zookeeper.setup(
            count=count,
            image=image,
            key=key,
            cidr_block=subnet_cidr_block,
            instance_type=instance_type,
            ipa_admin_password=ipa_admin_password,
            proid=proid,
            subnet_name=self.subnet_name
        )

    def setup_master(self, name, key, count, image, instance_type,
                     tm_release, app_root, ipa_admin_password, proid,
                     subnet_cidr_block=None):
        self.master = master.Master(name=name, vpc_id=self.vpc.id,)
        self.master.setup(
            image=image,
            count=count,
            cidr_block=subnet_cidr_block,
            key=key,
            tm_release=tm_release,
            instance_type=instance_type,
            app_root=app_root,
            ipa_admin_password=ipa_admin_password,
            proid=proid,
            subnet_name=self.subnet_name
        )
        self.show()

    def show(self):
        self.output = subnet.Subnet(
            name=self.subnet_name,
            vpc_id=self.vpc.id
        ).show()
        _LOGGER.info("******************************************************")
        _LOGGER.info(self.output)
        _LOGGER.info("******************************************************")
        return self.output
