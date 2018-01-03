yum install -y ipa-server haveged ipa-server-dns

systemctl enable haveged
systemctl start haveged

PRIVATE_IP=$(ip addr | grep 'state UP' -A2 | tail -n1 | awk '{print $2}' | cut -f1  -d'/')

ipa-server-install --unattended \
    --no-ntp --mkhomedir \
    --domain "{{ DOMAIN }}" \
    --realm "{{ DOMAIN|upper }}" \
    -a "{{ IPA_ADMIN_PASSWORD }}" \
    -p "{{ IPA_ADMIN_PASSWORD }}" \
    --setup-dns \
    --reverse-zone="{{ REVERSE_ZONE }}." \
    --forwarder "8.8.8.8" \
    --ip-address "${PRIVATE_IP}" \
    --allow-zone-overlap \

echo "{{ IPA_ADMIN_PASSWORD }}" | kinit admin

ipa dnszone-mod "{{ DOMAIN }}" --allow-sync-ptr=TRUE || echo "Skipping dnszon-mod"

ipa dnsrecord-add "{{ DOMAIN }}" ipa-ca --a-rec ${PRIVATE_IP} || echo "Skipping dnrecord-add. Probably already present."

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

ipa role-add "Service Admin" --desc "Service Admin"
ipa role-add-privilege "Service Admin" --privileges "Service Administrators"
ipa role-add-member "Service Admin" --users tmhostadm

kadmin.local -q "xst -norandkey -k /tmp/tmhostadm.keytab tmhostadm"
chown tmhostadm:tmhostadm /tmp/tmhostadm.keytab

(
cat <<EOF
su -c "kinit -k -t /tmp/tmhostadm.keytab tmhostadm" tmhostadm
EOF
) > /etc/cron.hourly/tmhostadm-kinit

chmod 755 /etc/cron.hourly/tmhostadm-kinit
/etc/cron.hourly/tmhostadm-kinit

nohup su -c "{{ TREADMILL }} sproc restapi -p 5108 --title 'Treadmill_API' \
    -m ipa,cloud --cors-origin='.*'" tmhostadm > /var/log/ipa_api.out 2>&1 &

TREADMLD_OUTPUT=$(ipa -n user-add --first="${PROID}" --last=proid --shell /bin/bash --class proid --random "${PROID}")
TMP_TREADMLD_PASSWORD=$(echo "${TREADMLD_OUTPUT}" | grep 'Random password:' | awk '{print $3}')
NEW_TREADMLD_PASSWORD=$(openssl rand -base64 12)

kpasswd "${PROID}" <<EOF
${TMP_TREADMLD_PASSWORD}
${NEW_TREADMLD_PASSWORD}
${NEW_TREADMLD_PASSWORD}
EOF

mkdir -m 700 -p /home/tmhostadm
chown tmhostadm:tmhostadm /home/tmhostadm
su -c 'echo source /etc/profile.d/treadmill_profile.sh >> ~/.bashrc' tmhostadm
