# Install

if [ ! -e /etc/yum.repos.d/cloudera-cdh5.repo ]; then
    curl -L https://archive.cloudera.com/cdh5/redhat/5/x86_64/cdh/cloudera-cdh5.repo?_ga=2.172934241.314812559.1496985621-1968320782.1496291714 -o /etc/yum.repos.d/cloudera-cdh5.repo
fi

yum -y install java
yum -y install zookeeper

# Configure

AMI_LAUNCH_INDEX=$(curl http://169.254.169.254/latest/meta-data/ami-launch-index)
ZK_ID=$((AMI_LAUNCH_INDEX+1))

echo $ZK_ID > /var/lib/zookeeper/myid

(
cat <<EOF
server.1=TreadmillZookeeper1.{{ DOMAIN }}:2888:3888
server.2=TreadmillZookeeper2.{{ DOMAIN }}:2888:3888
server.3=TreadmillZookeeper3.{{ DOMAIN }}:2888:3888
EOF
) >> /etc/zookeeper/conf/zoo.cfg

(
cat <<EOF
[Unit]
Description=Zookeeper distributed coordination server
After=network.target

[Service]
Type=forking
User=zookeeper
Group=zookeeper
SyslogIdentifier=zookeeper
Environment=ZOO_LOG_DIR=/var/lib/zookeeper
ExecStart=/usr/lib/zookeeper/bin/zkServer.sh start
ExecStop=/usr/lib/zookeeper/bin/zkServer.sh stop

[Install]
WantedBy=multi-user.target
EOF
) > /etc/systemd/system/zookeeper.service

chown -R zookeeper:zookeeper /var/lib/zookeeper
/bin/systemctl start zookeeper.service
