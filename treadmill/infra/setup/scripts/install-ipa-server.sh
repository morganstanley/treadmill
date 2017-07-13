yum install -y ipa-server

ipa-server-install --unattended \
    --no-ntp --mkhomedir \
    --domain "{{ DOMAIN }}" \
    --realm "{{ DOMAIN|upper }}" \
    -a "{{ IPA_ADMIN_PASSWORD }}" \
    -p "{{ IPA_ADMIN_PASSWORD }}"

echo "{{ IPA_ADMIN_PASSWORD }}" | kinit admin

TMHOSTADM_OUTPUT=$(ipa -n user-add tmhostadm --first tmhostadm --last proid --shell /bin/bash --class proid --random)
TMP_TMHOSTADM_PASSWORD=$(echo "${TMHOSTADM_OUTPUT}" | grep 'Random password:' | awk '{print $3}')
NEW_TMHOSTADM_PASSWORD=$(openssl rand -base64 12)

kpasswd tmhostadm <<EOF
${TMP_TMHOSTADM_PASSWORD}
${NEW_TMHOSTADM_PASSWORD}
${NEW_TMHOSTADM_PASSWORD}
EOF

ipa role-add "Host Enroller" --desc "Host Enroller"
ipa role-add-privilege "Host Enroller" --privileges "Host Enrollment"
ipa role-add-privilege "Host Enroller" --privileges "Host Administrators"
ipa role-add-member "Host Enroller" --users tmhostadm

kadmin.local -q "xst -norandkey -k /tmp/tmhostadm.keytab tmhostadm"
chown tmhostadm:tmhostadm /tmp/tmhostadm.keytab

(
cat <<EOF
su -c "kinit -k -t /tmp/tmhostadm.keytab tmhostadm" tmhostadm
EOF
) > /etc/cron.hourly/tmhostadm-kinit

chmod 755 /etc/cron.hourly/tmhostadm-kinit
/etc/cron.hourly/tmhostadm-kinit

export TREADMILL_CELL="{{ CELL }}"

nohup su -c "/bin/treadmill sproc restapi -p 8000 --title 'Treadmill_Cloud_Host_API' \
    -m cloud_host --cors-origin='.*'" tmhostadm > /var/log/cloud_host.out 2>&1 &

