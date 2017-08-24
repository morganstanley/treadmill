from treadmill.infra.setup import base_provision
from treadmill.infra import configuration, constants, instances


class Node(base_provision.BaseProvision):
    def setup(
            self,
            image,
            count,
            key,
            tm_release,
            instance_type,
            app_root,
            ldap_hostname,
            subnet_id,
            ipa_admin_password,
            with_api,
    ):
        self.configuration = configuration.Node(
            name=self.name,
            tm_release=tm_release,
            app_root=app_root,
            subnet_id=subnet_id,
            ldap_hostname=ldap_hostname,
            ipa_admin_password=ipa_admin_password,
            with_api=with_api,
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

        self.vpc.load_hosted_zone_ids()

        _instances.terminate(
            hosted_zone_id=self.vpc.hosted_zone_id,
            reverse_hosted_zone_id=self.vpc.reverse_hosted_zone_id
        )
