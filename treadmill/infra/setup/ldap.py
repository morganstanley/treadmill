from treadmill.infra.setup import base_provision
from treadmill.infra import configuration


class LDAP(base_provision.BaseProvision):
    def __init__(
            self,
            name,
            vpc_id,
    ):
        super(LDAP, self).__init__(
            name=name,
            vpc_id=vpc_id,
        )

    def setup(
            self,
            image_id,
            count,
            key,
            cidr_block,
            tm_release,
            instance_type,
            app_root,
            ldap_hostname,
            subnet_id=None
    ):
        self.configuration = configuration.LDAP(
            subnet_id=subnet_id,
            ldap_hostname=ldap_hostname,
            tm_release=tm_release,
            app_root=app_root,
            name=self.name
        )
        super(LDAP, self).setup(
            image_id=image_id,
            count=count,
            cidr_block=cidr_block,
            subnet_id=subnet_id,
            key=key,
            instance_type=instance_type
        )
