(
cat <<EOF
mkdir -p /etc/tickets
chown treadmld:treadmld /etc/tickets
su -c "kinit -k -t /etc/treadmld.keytab treadmld -c /etc/tickets/treadmld" treadmld
EOF
) > /etc/cron.hourly/treadmldkey-kinit

chmod 755 /etc/cron.hourly/treadmldkey-kinit
/etc/cron.hourly/treadmldkey-kinit

cat <<EOF >> /var/tmp/cellapi.yml
{% include 'manifests/cellapi.yml' %}
EOF

cat <<EOF >> /var/tmp/adminapi.yml
{% include 'manifests/adminapi.yml' %}
EOF

cat <<EOF >> /var/tmp/stateapi.yml
{% include 'manifests/stateapi.yml' %}
EOF

su -c "{{ TREADMILL }} admin master app schedule --env prod --proid treadmld --manifest /var/tmp/cellapi.yml treadmld.cellapi" treadmld
su -c "{{ TREADMILL }} admin master app schedule --env prod --proid treadmld --manifest /var/tmp/adminapi.yml treadmld.adminapi" treadmld
su -c "{{ TREADMILL }} admin master app schedule --env prod --proid treadmld --manifest /var/tmp/stateapi.yml treadmld.stateapi" treadmld

sleep 30

systemctl restart treadmill-node
