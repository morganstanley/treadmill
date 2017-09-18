from treadmill.infra.setup import base_provision
from treadmill.infra import configuration, constants, instances, connection
import time
from treadmill.api import ipa


class Node(base_provision.BaseProvision):
    def setup(
            self,
            image,
            count,
            key,
            tm_release,
            instance_type,
            app_root,
            subnet_id,
            with_api,
            ipa_admin_password
    ):
        # TODO: remove count as parameter
        count = 1
        self.name = self.name + '-' + str(time.time())
        self.hostname = self.name + '.' + connection.Connection.context.domain
        ldap_hostname = instances.Instances.get_hostnames_by_roles(
            vpc_id=self.vpc.id,
            roles=[
                constants.ROLES['LDAP'],
            ]
        )[constants.ROLES['LDAP']]

        otp = ipa.API().add_host({'hostname': self.hostname})
        self.configuration = configuration.Node(
            tm_release=tm_release,
            app_root=app_root,
            subnet_id=subnet_id,
            ldap_hostname=ldap_hostname,
            otp=otp,
            with_api=with_api,
            hostname=self.hostname,
            ipa_admin_password=ipa_admin_password
        )
        self.subnet_name = constants.TREADMILL_CELL_SUBNET_NAME
        super().setup(
            image=image,
            count=count,
            subnet_id=subnet_id,
            key=key,
            instance_type=instance_type
        )

    def destroy(self, instance_id=None):
        if instance_id:
            _instances = instances.Instances.get(ids=[instance_id])
        elif self.name:
            _instances = instances.Instances.get(
                filters=[
                    {
                        'Name': 'tag-key',
                        'Values': ['Name']
                    },
                    {
                        'Name': 'tag-value',
                        'Values': [self.name]
                    },
                ]
            )
        else:
            return

        _instances.terminate()
