# install
yum install -y ipa-client

# get OTP from IPA cloud-host service
HOST_FQDN=$(hostname -f)
REQ_URL="http://ipa-ca:8000/cloud-host/${HOST_FQDN}"

REQ_STATUS=254
TIMEOUT_RETRY_COUNT=0
while [ $REQ_STATUS -eq 254 ] && [ $TIMEOUT_RETRY_COUNT -ne 30 ]
do
    REQ_OUTPUT=$(curl --connect-timeout 5 -d "hostname=${HOST_FQDN}" "${REQ_URL}" 2>&1) && REQ_STATUS=0 || REQ_STATUS=254
    TIMEOUT_RETRY_COUNT=$((TIMEOUT_RETRY_COUNT+1))
    sleep 60
done

if [ $REQ_STATUS -eq 0 ] ; then
    ONE_TIME_PASSWORD=$(echo "$REQ_OUTPUT"|tail -1|cut -d '"' -f 2)
    if [ "$ONE_TIME_PASSWORD" = "message" ] ; then
        echo "Failed to add $HOST_FQDN to IPA"
        echo "$REQ_OUTPUT"|tail -1
        exit 253
    else
        ipa-client-install --unattended --no-ntp \
            --mkhomedir --no-krb5-offline-password \
            --password "$ONE_TIME_PASSWORD"
    fi
else
    echo "Failed to add $HOST_FQDN to IPA"
    echo "$REQ_OUTPUT"|tail -1
    exit $REQ_STATUS
fi

