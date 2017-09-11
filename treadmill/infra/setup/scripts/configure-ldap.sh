echo Installing openldap

yum -y install openldap openldap-clients openldap-servers ipa-admintools

echo Adding host to service keytab retrieval list

REQ_URL="http://ipa-ca:8000/cloud-host/ipa/service"
REQ_STATUS=254
TIMEOUT_RETRY_COUNT=0
while [ $REQ_STATUS -eq 254 ] && [ $TIMEOUT_RETRY_COUNT -ne 30 ]
do
    REQ_OUTPUT=$(curl --connect-timeout 5 -H "Content-Type: application/json" -X POST -d '{"domain": "{{ DOMAIN }}", "hostname": "'${HOST_FQDN}'", "service": "'ldap/$HOST_FQDN'"}' "${REQ_URL}" 2>&1) && REQ_STATUS=0 || REQ_STATUS=254
    TIMEOUT_RETRY_COUNT=$((TIMEOUT_RETRY_COUNT+1))
    sleep 60
done

kinit -kt /etc/krb5.keytab

echo Retrieving ldap service keytab
ipa-getkeytab -s "{{ IPA_SERVER_HOSTNAME }}" -p "ldap/$HOST_FQDN@{{ DOMAIN|upper }}" -k /etc/ldap.keytab

ipa-getkeytab -r -p treadmld -D "cn=Directory Manager" -w "{{ IPA_ADMIN_PASSWORD }}" -k /etc/treadmld.keytab
chown treadmld:treadmld /etc/ldap.keytab /etc/treadmld.keytab

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

s6-setuidgid treadmld \
    {{ TREADMILL }} admin install --install-dir /var/tmp/treadmill-openldap \
        openldap \
        --owner treadmld \
        --uri ldap://0.0.0.0:22389 \
        --suffix "${LDAP_DC}" \
        --gssapi

# TODO: Create global utility function for adding service
systemctl daemon-reload
systemctl enable openldap.service --now
systemctl status openldap

echo Initializing openldap

su -c "kinit -k -t /etc/treadmld.keytab treadmld" treadmld

s6-setuidgid treadmld {{ TREADMILL }} admin ldap init

(
# FIXME: Flaky command. Works after a few re-runs.
TIMEOUT=120

retry_count=0
until ( s6-setuidgid treadmld {{ TREADMILL }} admin ldap schema --update ) || [ $retry_count -eq $TIMEOUT ]
do
    retry_count=`expr $retry_count + 1`
    echo "Trying ldap schema update : $retry_count"
    sleep 1
done
)
