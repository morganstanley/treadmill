from treadmill.infra.setup import base_provision
from treadmill.infra import configuration, constants


class Node(base_provision.BaseProvision):
    def __init__(
            self,
            name,
            vpc_id,
    ):
        super(Node, self).__init__(
            name=name,
            vpc_id=vpc_id,
        )
        self.subnet_name = constants.TREADMILL_CELL_SUBNET_NAME

    def setup(
            self,
            image_id,
            count,
            key,
            tm_release,
            instance_type,
            app_root,
            ldap_hostname,
            subnet_id
    ):
        self.configuration = configuration.Node(
            name=self.name,
            tm_release=tm_release,
            app_root=app_root,
            subnet_id=subnet_id,
            ldap_hostname=ldap_hostname,
        )
        super(Node, self).setup(
            image_id=image_id,
            count=count,
            subnet_id=subnet_id,
            key=key,
            instance_type=instance_type
        )
