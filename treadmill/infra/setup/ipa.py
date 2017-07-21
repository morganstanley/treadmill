from treadmill.infra import constants
from treadmill.infra.setup import base_provision
from treadmill.infra import configuration, connection


class IPA(base_provision.BaseProvision):
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
            tm_release=tm_release
        )
        super().setup(
            image_id=image_id,
            count=count,
            cidr_block=cidr_block,
            subnet_id=subnet_id,
            key=key,
            instance_type=instance_type
        )

        self._update_route53('UPSERT')

    def destroy(self, subnet_id):
        super().destroy(
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
        for instance in self.subnet.instances.instances:
            for _rec, _value in srv_records.items():
                self._change_srv_record(
                    action=action,
                    name=self._rec_name(_rec),
                    value=self._srv_rec_value(_value, instance.name),
                    record_type='SRV'
                )
            self._change_srv_record(
                action=action,
                name=self._rec_name('ipa-ca'),
                value=self.subnet.instances.instances[0].private_ip,
                record_type='A'
            )
            self._change_srv_record(
                action=action,
                name=self._rec_name('_kerberos'),
                value='"{0}"'.format(
                    connection.Connection.context.domain.upper()
                ),
                record_type='TXT'
            )

    def _rec_name(self, rec):
        return rec + '.' + connection.Connection.context.domain + '.'

    def _srv_rec_value(self, value, instance_name):
        return value + ' ' + instance_name + '.' \
            + connection.Connection.context.domain + '.'

    def _change_srv_record(self,
                           action,
                           name,
                           value,
                           record_type):
        self.route_53_conn.change_resource_record_sets(
            HostedZoneId=self.vpc.hosted_zone_id.split('/')[-1],
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
