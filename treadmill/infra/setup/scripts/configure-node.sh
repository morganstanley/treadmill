setenforce 0
sed -i -e 's/SELINUX=enforcing/SELINUX=permissive/g' /etc/selinux/config

echo Installing Node packages
yum -y install conntrack-tools iproute libcgroup libcgroup-tools bridge-utils openldap-clients lvm2* ipset iptables rrdtool

source /etc/profile.d/treadmill_profile.sh

kinit -k

(
TIMEOUT=30
retry_count=0
until ( ldapsearch -c -H $TREADMILL_LDAP "ou=cells" ) || [ $retry_count -eq $TIMEOUT ]
do
    retry_count=$(($retry_count+1))
    sleep 30
done
)

{{ TREADMILL }} --outfmt yaml admin ldap cell configure "{{ SUBNET_ID }}" > /var/tmp/cell_conf.yml

(
cat <<EOF
mkdir -p /var/spool/tickets
kinit -k -t /etc/krb5.keytab -c /var/spool/tickets/"${PROID}"
chown "${PROID}":"${PROID}" /var/spool/tickets/"${PROID}"
EOF
) > /etc/cron.hourly/hostkey-"${PROID}"-kinit

chmod 755 /etc/cron.hourly/hostkey-"${PROID}"-kinit
/etc/cron.hourly/hostkey-"${PROID}"-kinit

(
cat <<EOF
[Unit]
Description=Treadmill node services
After=network.target

[Service]
User=root
Group=root
SyslogIdentifier=treadmill
ExecStartPre=/bin/mount --make-rprivate /
ExecStart={{ APP_ROOT }}/bin/run.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
) > /etc/systemd/system/treadmill-node.service

{{ TREADMILL }} admin install \
    --install-dir {{ APP_ROOT }} \
    --config /var/tmp/cell_conf.yml \
    --override "network_device=eth0 rrdtool=/usr/bin/rrdtool rrdcached=/usr/bin/rrdcached" \
    node

ipa-getkeytab -r -p "${PROID}" -D "cn=Directory Manager" -w "{{ IPA_ADMIN_PASSWORD }}" -k /etc/"${PROID}".keytab
chown "${PROID}":"${PROID}" /etc/"${PROID}".keytab
su -c "kinit -k -t /etc/${PROID}.keytab ${PROID}" "${PROID}"

s6-setuidgid "${PROID}" {{ TREADMILL }} admin ldap server configure "$(hostname -f)" --cell "{{ SUBNET_ID }}"

/bin/systemctl daemon-reload
/bin/systemctl enable treadmill-node.service --now

ln -s /var/spool/tickets/"${PROID}" {{ APP_ROOT }}/spool/krb5cc_host
