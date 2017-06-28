from treadmill.infra import constants
from treadmill.infra.setup import base_provision
from treadmill.infra import configuration


class IPA(base_provision.BaseProvision):
    def __init__(
            self,
            name,
            vpc_id,
            domain,
    ):
        super(IPA, self).__init__(
            name=name,
            vpc_id=vpc_id,
            domain=domain,
        )

    def setup(
            self,
            image_id,
            count,
            cidr_block,
            ipa_admin_password,
            tm_release,
            key,
            instance_type,
            subnet_id=None
    ):

        self.configuration = configuration.IPA(
            name=self.name,
            cell=subnet_id,
            ipa_admin_password=ipa_admin_password,
            domain=self.domain,
            tm_release=tm_release
        )
        super(IPA, self).setup(
            image_id=image_id,
            count=count,
            cidr_block=cidr_block,
            subnet_id=subnet_id,
            key=key,
            instance_type=instance_type
        )

        self._update_route53('UPSERT')

    def destroy(self, subnet_id):
        super(IPA, self).destroy(
            subnet_id=subnet_id
        )

        self._update_route53('DELETE')

    def _update_route53(self, action):
        srv_records = {
            '_kerberos-master._tcp': '0 100 88',
            '_kerberos-master._udp': '0 100 88',
            '_kerberos._tcp': '0 100 88',
            '_kerberos._udp': '0 100 88',
            '_kpasswd._tcp': '0 100 464',
            '_kpasswd._udp': '0 100 464',
            '_ldap._tcp': '0 100 389',
            '_ntp._udp': '0 100 123'
        }

        for _rec, _value in srv_records.items():
            self._change_srv_record(
                action=action,
                hosted_zone_id=self.vpc.hosted_zone_id,
                name=self._rec_name(_rec),
                value=self._srv_rec_value(_value),
                record_type='SRV'
            )
        self._change_srv_record(
            action=action,
            hosted_zone_id=self.vpc.hosted_zone_id,
            name=self._rec_name('ipa-ca'),
            value=self.subnet.instances.instances[0].private_ip,
            record_type='A'
        )
        self._change_srv_record(
            action=action,
            hosted_zone_id=self.vpc.hosted_zone_id,
            name=self._rec_name('_kerberos'),
            value='"{0}"'.format(self.domain.upper()),
            record_type='TXT'
        )

    def _rec_name(self, name):
        return name + '.' + self.domain + '.'

    def _srv_rec_value(self, value):
        return value + ' ' + self.name + '.' + self.domain + '.'

    def _change_srv_record(self,
                           action,
                           hosted_zone_id,
                           name,
                           value,
                           record_type):
        self.route_53_conn.change_resource_record_sets(
            HostedZoneId=hosted_zone_id.split('/')[-1],
            ChangeBatch={
                'Changes': [{
                    'Action': action,
                    'ResourceRecordSet': {
                        'Name': name,
                        'Type': record_type,
                        'TTL': constants.IPA_ROUTE_53_RECORD_SET_TTL,
                        'ResourceRecords': [{
                            'Value': value
                        }]
                    }
                }]
            }
        )
