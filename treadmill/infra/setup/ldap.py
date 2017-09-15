from treadmill.infra.setup import base_provision
from treadmill.infra import configuration
from treadmill.infra import instances


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
            ldap_hostname,
            ipa_admin_password,
            proid,
            subnet_name,
            subnet_id=None
    ):
        ipa_server_hostname = instances.Instances.get_ipa(
            vpc_id=self.vpc.id
        ).hostname

        self.configuration = configuration.LDAP(
            ldap_hostname=ldap_hostname,
            tm_release=tm_release,
            app_root=app_root,
            name=self.name,
            ipa_admin_password=ipa_admin_password,
            ipa_server_hostname=ipa_server_hostname,
            proid=proid
        )
        super().setup(
            image=image,
            count=count,
            cidr_block=cidr_block,
            subnet_id=subnet_id,
            key=key,
            instance_type=instance_type,
            subnet_name=subnet_name
        )
