from treadmill.infra.setup import base_provision
from treadmill.infra import configuration


class Master(base_provision.BaseProvision):
    def __init__(
            self,
            name,
            vpc_id,
            domain,
    ):
        super(Master, self).__init__(
            name=name,
            vpc_id=vpc_id,
            domain=domain,
        )

    def setup(
            self,
            image_id,
            count,
            cidr_block,
            ldap_hostname,
            tm_release,
            key,
            instance_type,
            app_root,
            subnet_id=None,
    ):
        self.configuration = configuration.Master(
            name=self.name,
            subnet_id=subnet_id,
            ldap_hostname=ldap_hostname,
            domain=self.domain,
            tm_release=tm_release,
            app_root=app_root
        )
        super(Master, self).setup(
            image_id=image_id,
            count=count,
            cidr_block=cidr_block,
            subnet_id=subnet_id,
            key=key,
            instance_type=instance_type
        )
