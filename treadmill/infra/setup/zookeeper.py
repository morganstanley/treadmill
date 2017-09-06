from treadmill.infra.setup import base_provision
from treadmill.infra import configuration, constants
from treadmill.infra import instances


class Zookeeper(base_provision.BaseProvision):
    def setup(self, image, key, cidr_block, instance_type, ldap_hostname,
              ipa_admin_password, subnet_id=None):
        ipa_server_hostname = instances.Instances.get_ipa(
            vpc_id=self.vpc.id
        ).hostname

        self.configuration = configuration.Zookeeper(
            self.name,
            ldap_hostname,
            ipa_server_hostname
        )
        self.subnet_name = constants.TREADMILL_CELL_SUBNET_NAME
        super().setup(
            image=image,
            count=3,
            cidr_block=cidr_block,
            subnet_id=subnet_id,
            key=key,
            instance_type=instance_type
        )
