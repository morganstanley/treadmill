from treadmill.infra.setup import base_provision
from treadmill.infra import configuration, connection, constants, instances
from treadmill.api import ipa
import time


class LDAP(base_provision.BaseProvision):
    def setup(
            self,
            image,
            count,
            key,
            cidr_block,
            tm_release,
            instance_type,
            app_root,
            cell_subnet_id,
            ipa_admin_password,
            subnet_id=None
    ):
        # TODO: remove count as parameter
        count = 1
        self.name = self.name + '-' + str(time.time())
        hostname = self.name + '.' + connection.Connection.context.domain
        otp = ipa.API().add_host(hostname=hostname)

        ipa_server_hostname = instances.Instances.get_hostnames_by_roles(
            vpc_id=self.vpc.id,
            roles=[
                constants.ROLES['IPA']
            ]
        )[constants.ROLES['IPA']]

        self.configuration = configuration.LDAP(
            cell_subnet_id=cell_subnet_id,
            tm_release=tm_release,
            app_root=app_root,
            hostname=hostname,
            ipa_admin_password=ipa_admin_password,
            ipa_server_hostname=ipa_server_hostname,
            otp=otp
        )
        super().setup(
            image=image,
            count=count,
            cidr_block=cidr_block,
            subnet_id=subnet_id,
            key=key,
            instance_type=instance_type
        )
