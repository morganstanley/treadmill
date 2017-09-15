from treadmill.infra.setup import base_provision
from treadmill.infra import configuration
from treadmill.infra import instances


class Zookeeper(base_provision.BaseProvision):
    def setup(self, image, key, cidr_block, instance_type, ldap_hostname,
              proid, subnet_name, subnet_id=None):
        ipa_server_hostname = instances.Instances.get_ipa(
            vpc_id=self.vpc.id
        ).hostname

        self.configuration = configuration.Zookeeper(
            self.name,
            ldap_hostname,
            ipa_server_hostname,
            proid
        )
        super().setup(
            image=image,
            count=3,
            cidr_block=cidr_block,
            subnet_id=subnet_id,
            key=key,
            instance_type=instance_type,
            subnet_name=subnet_name
        )
