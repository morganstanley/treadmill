# install
yum install -y ipa-client ipa-server-dns

ipa-client-install --unattended --no-ntp \
    --mkhomedir --no-krb5-offline-password \
    --password "{{ OTP }}" --enable-dns-updates
