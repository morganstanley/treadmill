echo Installing openldap

yum -y install openldap openldap-clients openldap-servers ipa-admintools

HOST_FQDN=$(hostname -f)

kinit -kt /etc/krb5.keytab

echo Retrieving LDAP service keytab
ipa-getkeytab -s "{{ IPA_SERVER_HOSTNAME }}" -p "ldap/$HOST_FQDN@{{ DOMAIN|upper }}" -k /etc/ldap.keytab
ipa-getkeytab -r -p "${PROID}" -D "cn=Directory Manager" -w "{{ IPA_ADMIN_PASSWORD }}" -k /etc/"${PROID}".keytab
chown "${PROID}":"${PROID}" /etc/ldap.keytab /etc/"${PROID}".keytab

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
Environment="KRB5_KTNAME=/etc/ldap.keytab"
User=${PROID}
Group=${PROID}
SyslogIdentifier=openldap
ExecStart=/var/tmp/treadmill-openldap/bin/run.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
) > /etc/systemd/system/openldap.service

s6-setuidgid "${PROID}" \
    {{ TREADMILL }} admin install --install-dir /var/tmp/treadmill-openldap \
        openldap \
        --owner "${PROID}" \
        --uri ldap://0.0.0.0:22389 \
        --suffix "${LDAP_DC}" \
        --gssapi

# TODO: Create global utility function for adding service
systemctl daemon-reload
systemctl enable openldap.service --now
systemctl status openldap

echo Initializing openldap

su -c "kinit -k -t /etc/${PROID}.keytab ${PROID}" "${PROID}"

s6-setuidgid "${PROID}" {{ TREADMILL }} admin ldap init

(
# FIXME: Flaky command. Works after a few re-runs.
TIMEOUT=120

retry_count=0
until ( s6-setuidgid "${PROID}" {{ TREADMILL }} admin ldap schema --update ) || [ $retry_count -eq $TIMEOUT ]
do
    retry_count=`expr $retry_count + 1`
    echo "Trying ldap schema update : $retry_count"
    sleep 1
done
)
