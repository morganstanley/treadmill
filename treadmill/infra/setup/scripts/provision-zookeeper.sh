# Install

if [ ! -e /etc/yum.repos.d/treadmill.repo ]; then
    curl -L https://s3.amazonaws.com/yum_repo_dev/treadmill.repo -o /etc/yum.repos.d/treadmill.repo
fi

yum -y install java
yum -y install zookeeper-ldap-plugin --nogpgcheck

# Configure

(
cat <<EOF
server.1=TreadmillZookeeper1.{{ DOMAIN }}:2888:3888
server.2=TreadmillZookeeper2.{{ DOMAIN }}:2888:3888
server.3=TreadmillZookeeper3.{{ DOMAIN }}:2888:3888
EOF
) >> /etc/zookeeper/conf/zoo.cfg

mac_addr=`cat /sys/class/net/eth0/address`
subnet_id=`curl http://169.254.169.254/latest/meta-data/network/interfaces/macs/$mac_addr/subnet-id`
HOST_FQDN=$(hostname -f)

export TREADMILL_CELL=$subnet_id

echo Adding host to service keytab retrieval list

REQ_URL="http://ipa-ca:8000/cloud-host/ipa/service"
REQ_STATUS=254
TIMEOUT_RETRY_COUNT=0
while [ $REQ_STATUS -eq 254 ] && [ $TIMEOUT_RETRY_COUNT -ne 30 ]
do
    REQ_OUTPUT=$(curl --connect-timeout 5 -H "Content-Type: application/json" -X POST -d '{"domain": "{{ DOMAIN }}", "hostname": "'${HOST_FQDN}'", "service": "'zookeeper/$HOST_FQDN'"}' "${REQ_URL}" 2>&1) && REQ_STATUS=0 || REQ_STATUS=254
    TIMEOUT_RETRY_COUNT=$((TIMEOUT_RETRY_COUNT+1))
    sleep 60
done

kinit -kt /etc/krb5.keytab

echo Retrieving zookeeper service keytab
ipa-getkeytab -s "{{ IPA_SERVER_HOSTNAME }}" -p "zookeeper/$HOST_FQDN@{{ DOMAIN|upper }}" -k /etc/zk.keytab

envsubst < /etc/zookeeper/conf/treadmill.conf > /etc/zookeeper/conf/temp.conf
mv /etc/zookeeper/conf/temp.conf /etc/zookeeper/conf/treadmill.conf -f
sed -i s/REALM/{{ DOMAIN|upper }}/g /etc/zookeeper/conf/treadmill.conf
sed -i s/PRINCIPAL/'"'zookeeper\\/$HOST_FQDN'"'/g /etc/zookeeper/conf/jaas.conf
sed -i s/KEYTAB/'"'\\/etc\\/zk.keytab'"'/g /etc/zookeeper/conf/jaas.conf

(
cat <<EOF
[Unit]
Description=Zookeeper distributed coordination server
After=network.target

[Service]
Type=forking
User=treadmld
Group=treadmld
SyslogIdentifier=zookeeper
Environment=ZOO_LOG_DIR=/var/lib/zookeeper
ExecStart=/usr/lib/zookeeper/bin/zkServer.sh start
ExecStop=/usr/lib/zookeeper/bin/zkServer.sh stop

[Install]
WantedBy=multi-user.target
EOF
) > /etc/systemd/system/zookeeper.service

chown -R treadmld:treadmld /var/lib/zookeeper

su -c "zookeeper-server-initialize" treadmld

AMI_LAUNCH_INDEX=$(curl http://169.254.169.254/latest/meta-data/ami-launch-index)
ZK_ID=$((AMI_LAUNCH_INDEX+1))
su -c "echo $ZK_ID > /var/lib/zookeeper/myid" treadmld

chown treadmld:treadmld /etc/zk.keytab
kinit -k

/bin/systemctl enable zookeeper.service
/bin/systemctl start zookeeper.service
