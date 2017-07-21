AMI_LAUNCH_INDEX=$(curl -s http://169.254.169.254/latest/meta-data/ami-launch-index)
MASTER_ID=$(expr $AMI_LAUNCH_INDEX + 1) # AMI_LAUNCH_INDEX is 0 indexed, master cannot be set to 0.

yum install -y openldap-clients
source /etc/profile.d/treadmill_profile.sh

kinit -k

(
TIMEOUT=30
retry_count=0
until ( ldapsearch -c -H $TREADMILL_LDAP ) || [ $retry_count -eq $TIMEOUT ]
do
    retry_count=$(($retry_count+1))
    sleep 30
done
)

ipa-getkeytab -r -p treadmld -D "cn=Directory Manager" -w "{{ IPA_ADMIN_PASSWORD }}" -k /etc/treadmld.keytab
chown treadmld:treadmld /etc/treadmld.keytab
su -c "kinit -k -t /etc/treadmld.keytab treadmld" treadmld

s6-setuidgid treadmld \
    {{ TREADMILL }} admin ldap cell configure "{{ SUBNET_ID }}" --version 0.1 --root "{{ APP_ROOT }}" \
        --username treadmld \
        --location local.local

s6-setuidgid treadmld \
    {{ TREADMILL }} admin ldap cell insert "{{ SUBNET_ID }}" --idx "${MASTER_ID}" \
        --hostname "$(hostname -f)" --client-port 2181

{{ TREADMILL }} --outfmt yaml admin ldap cell configure "{{ SUBNET_ID }}" > /var/tmp/cell_conf.yml

(
cat <<EOF
mkdir -p /var/spool/tickets
kinit -k -t /etc/krb5.keytab -c /var/spool/tickets/treadmld
chown treadmld:treadmld /var/spool/tickets/treadmld
EOF
) > /etc/cron.hourly/hostkey-treadmld-kinit

chmod 755 /etc/cron.hourly/hostkey-treadmld-kinit
/etc/cron.hourly/hostkey-treadmld-kinit

# Install master service
{{ TREADMILL }} admin install --install-dir /var/tmp/treadmill-master \
    --override "profile=cloud" \
    --config /var/tmp/cell_conf.yml master --master-id "${MASTER_ID}"

(
cat <<EOF
[Unit]
Description=Treadmill master services
After=network.target

[Service]
User=root
Group=root
SyslogIdentifier=treadmill
ExecStartPre=/bin/mount --make-rprivate /
ExecStart=/var/tmp/treadmill-master/treadmill/bin/run.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
) > /etc/systemd/system/treadmill-master.service


/bin/systemctl daemon-reload
/bin/systemctl enable treadmill-master.service --now
