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

systemctl restart treadmill-node
