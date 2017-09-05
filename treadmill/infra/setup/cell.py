import logging

from treadmill.infra import vpc, subnet
from treadmill.infra.setup import master, zookeeper

_LOGGER = logging.getLogger(__name__)


class Cell:
    def __init__(self, subnet_id=None, vpc_id=None):
        self.vpc = vpc.VPC(id=vpc_id)
        self.master = master.Master(
            name=None,
            vpc_id=self.vpc.id,
        )
        self.master.subnet = subnet.Subnet(id=subnet_id)
        self.id = subnet_id

    def setup_vpc(
            self,
            vpc_cidr_block,
            secgroup_name,
            secgroup_desc
    ):
        if not self.vpc.id:
            self.vpc.create(vpc_cidr_block)
        else:
            self.vpc.refresh()

        self.vpc.create_internet_gateway()
        self.vpc.create_security_group(secgroup_name, secgroup_desc)

    def setup_zookeeper(self, name, key, image, instance_type,
                        subnet_cidr_block, ldap_hostname, ipa_admin_password,
                        proid, subnet_name):
        self.zookeeper = zookeeper.Zookeeper(name, self.vpc.id)
        self.zookeeper.setup(
            image=image,
            key=key,
            cidr_block=subnet_cidr_block,
            instance_type=instance_type,
            ldap_hostname=ldap_hostname,
            proid=proid,
            subnet_id=self.id,
            subnet_name=subnet_name
        )
        if not self.id:
            self.id = self.zookeeper.subnet.id

    def setup_master(self, name, key, count, image, instance_type,
                     tm_release, ldap_hostname, app_root,
                     ipa_admin_password, proid, subnet_name,
                     subnet_cidr_block=None):
        if not self.vpc.id:
            raise('Provide vpc_id in init or setup vpc prior.')

        self.master.name = name
        self.master.setup(
            image=image,
            count=count,
            cidr_block=subnet_cidr_block,
            key=key,
            ldap_hostname=ldap_hostname,
            tm_release=tm_release,
            instance_type=instance_type,
            app_root=app_root,
            subnet_id=self.id,
            ipa_admin_password=ipa_admin_password,
            proid=proid,
            subnet_name=subnet_name
        )
        self.show()

    def destroy(self):
        self.master.subnet.destroy()

    def show(self):
        self.output = self.master.subnet.show()
        _LOGGER.info("******************************************************")
        _LOGGER.info(self.output)
        _LOGGER.info("******************************************************")
        return self.output
