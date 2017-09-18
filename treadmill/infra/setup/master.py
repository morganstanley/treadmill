from treadmill.infra.setup import base_provision
from treadmill.infra import configuration, constants, connection, instances
from treadmill.api import ipa


class Master(base_provision.BaseProvision):
    def setup(
            self,
            image,
            count,
            cidr_block,
            tm_release,
            key,
            instance_type,
            app_root,
            ipa_admin_password,
            subnet_id=None,
    ):
        ldap_hostname = instances.Instances.get_hostnames_by_roles(
            vpc_id=self.vpc.id,
            roles=[
                constants.ROLES['LDAP'],
            ]
        )[constants.ROLES['LDAP']]

        self.subnet_name = constants.TREADMILL_CELL_SUBNET_NAME

        _hostnames = {}
        for _idx in range(0, count):
            _idx_s = str(_idx + 1)

            _hostnames[
                self.name + _idx_s + connection.Connection.context.domain
            ] = _idx_s

        def _subnet_id(subnet_id):
            if getattr(self, 'subnet', None) and self.subnet.id:
                return self.subnet.id
            else:
                return subnet_id

        _ipa = ipa.API()
        _name = self.name
        for _master_h in _hostnames.keys():
            _otp = _ipa.add_host({'hostname': _master_h})
            _idx = _hostnames[_master_h]
            self.configuration = configuration.Master(
                hostname=_master_h,
                otp=_otp,
                subnet_id=subnet_id,
                ldap_hostname=ldap_hostname,
                tm_release=tm_release,
                app_root=app_root,
                ipa_admin_password=ipa_admin_password,
                idx=_idx
            )
            self.name = _name + _idx
            super().setup(
                image=image,
                count=1,
                cidr_block=cidr_block,
                subnet_id=_subnet_id(subnet_id),
                key=key,
                instance_type=instance_type
            )
