import treadmill
from treadmill.infra.setup import base_provision
from treadmill.infra import configuration, constants
import polling
import time


class IPA(base_provision.BaseProvision):
    @property
    def metadata(self):
        return self.subnet.show(constants.ROLES['IPA'])['Instances'][0]

    def setup(
            self,
            image,
            count,
            cidr_block,
            ipa_admin_password,
            tm_release,
            key,
            instance_type,
            subnet_id=None
    ):
        treadmill.infra.get_iam_role(
            name=constants.IPA_EC2_IAM_ROLE,
            create=True
        )

        self.configuration = configuration.IPA(
            name=self.name,
            cell=subnet_id,
            vpc=self.vpc,
            ipa_admin_password=ipa_admin_password,
            tm_release=tm_release,
        )
        super().setup(
            image=image,
            count=count,
            cidr_block=cidr_block,
            subnet_id=subnet_id,
            key=key,
            instance_type=instance_type
        )

        def get_ipa_status():
            while self.metadata['InstanceState'] != 'running':
                time.sleep(2)
            return self.ec2_conn.describe_instance_status(
                InstanceIds=[self.metadata['InstanceId']]
            )['InstanceStatuses'][0]['InstanceStatus']['Details'][0]['Status']

        polling.poll(
            lambda: get_ipa_status() == 'passed',
            step=10,
            timeout=600
        )
        self.vpc.associate_dhcp_options([
            {
                'Key': 'domain-name-servers',
                'Values': [self.metadata['PrivateIpAddress']]
            }
        ])

    def destroy(self, subnet_id):
        super().destroy(
            subnet_id=subnet_id
        )
