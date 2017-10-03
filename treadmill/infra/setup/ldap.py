from treadmill.infra.setup import base_provision
from treadmill.infra import configuration, constants, exceptions, connection
from treadmill.api import ipa


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
            ipa_admin_password,
            proid,
            subnet_name,
    ):
        ipa_server_hostname, = self.hostnames_for(
            roles=[constants.ROLES['IPA']]
        )

        if not ipa_server_hostname:
            raise exceptions.IPAServerNotFound()

        _ldap_hostnames = self._hostname_cluster(count=count)
        _ipa = ipa.API()

        for _idx in _ldap_hostnames.keys():
            _ldap_h = _ldap_hostnames[_idx]
            otp = _ipa.add_host(hostname=_ldap_h)
            _ipa.service_add('ldap', _ldap_h, {
                'domain': connection.Connection.context.domain,
                'hostname': _ldap_h,
            })
            self.name = _ldap_h
            self.configuration = configuration.LDAP(
                tm_release=tm_release,
                app_root=app_root,
                hostname=_ldap_h,
                ipa_admin_password=ipa_admin_password,
                ipa_server_hostname=ipa_server_hostname,
                otp=otp,
                proid=proid
            )
            super().setup(
                image=image,
                count=count,
                cidr_block=cidr_block,
                key=key,
                instance_type=instance_type,
                subnet_name=subnet_name,
                sg_names=[constants.COMMON_SEC_GRP],
            )
