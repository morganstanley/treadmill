# install
yum install -y ipa-client

# configure
ipa-client-install --unattended --no-ntp \
    --mkhomedir --no-krb5-offline-password \
    --password "{{ ONE_TIME_PASSWORD }}"

