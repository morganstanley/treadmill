echo Installing openldap

yum -y install openldap openldap-clients openldap-servers

# Enable 22389 port for LDAP (requires policycoreutils-python)
/sbin/semanage  port -a -t ldap_port_t -p tcp 22389
/sbin/semanage  port -a -t ldap_port_t -p udp 22389

setenforce 0
sed -i -e 's/SELINUX=enforcing/SELINUX=permissive/g' /etc/selinux/config

# Add openldap service
(
cat <<EOF
[Unit]
Description=OpenLDAP Directory Server
After=network.target

[Service]
User=treadmld
Group=treadmld
SyslogIdentifier=openldap
ExecStart=/var/tmp/treadmill-openldap/bin/run.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
) > /etc/systemd/system/openldap.service

# XXX: Do we want to have a pre-set password?
s6-setuidgid treadmld \
    treadmill admin install --install-dir /var/tmp/treadmill-openldap \
        openldap \
        --owner treadmld \
        --uri ldap://0.0.0.0:22389 \
        --suffix ${LDAP_DC} \
        --rootpw $(/usr/sbin/slappasswd -s secret) \
        --enable-sasl \
        --ldap-hostname {{ LDAP_HOSTNAME }}

# TODO: Create global utility function for adding service
systemctl daemon-reload
systemctl enable openldap.service --now

echo Initializing openldap

s6-setuidgid treadmld \
    treadmill admin ldap init

s6-setuidgid treadmld \
    treadmill admin ldap schema --update

echo Configuring local cell

s6-setuidgid treadmld \
    treadmill admin ldap cell configure {{ SUBNET_ID }} --version 0.1 --root {{ APP_ROOT }} \
        --username treadmld \
        --location local.local
