(
cat <<EOF
mkdir -p /etc/tickets
chown ${PROID}:${PROID} /etc/tickets
su -c "kinit -k -t /etc/${PROID}.keytab ${PROID} -c /etc/tickets/${PROID}" ${PROID}
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

su -c "{{ TREADMILL }} admin master app schedule --env prod --proid ${PROID} --manifest /var/tmp/cellapi.yml ${PROID}.cellapi" "${PROID}"
su -c "{{ TREADMILL }} admin master app schedule --env prod --proid ${PROID} --manifest /var/tmp/adminapi.yml ${PROID}.adminapi" "${PROID}"
su -c "{{ TREADMILL }} admin master app schedule --env prod --proid ${PROID} --manifest /var/tmp/stateapi.yml ${PROID}.stateapi" "${PROID}"

sleep 30

systemctl restart treadmill-node
