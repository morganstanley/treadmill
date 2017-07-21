# install
yum clean all
rpm -ivh https://dl.fedoraproject.org/pub/epel/7/x86_64/e/epel-release-7-10.noarch.rpm
yum -y install python34

# Configure
AMI_LAUNCH_INDEX=$(curl http://169.254.169.254/latest/meta-data/ami-launch-index)
ID=$((AMI_LAUNCH_INDEX+1))
LDAP_DC=ou=treadmill,$(echo "{{ DOMAIN }}" | sed -E 's/([a-z]*)\.([a-z]*)/dc=\1,dc=\2/g')
LDAP_URL=ldap://{{ LDAP_HOSTNAME }}.{{ DOMAIN }}:22389
ZK_URL=zookeeper://foo@TreadmillZookeeper1.{{ DOMAIN }}:2181,TreadmillZookeeper2.{{ DOMAIN }}:2181,TreadmillZookeeper3.{{ DOMAIN }}:2181

hostnamectl set-hostname "{{ NAME }}${ID}.{{ DOMAIN }}"

grep -q -F 'preserve_hostname: true' /etc/cloud/cloud.cfg || echo 'preserve_hostname: true' >> /etc/cloud/cloud.cfg

# Setup environment vars
(
cat <<EOF
export TREADMILL_ZOOKEEPER=$ZK_URL
export TREADMILL_LDAP=$LDAP_URL
export TREADMILL_LDAP_SUFFIX=dc=${LDAP_DC}
export TREADMILL_CELL={{ SUBNET_ID }}
export TREADMILL_APPROOT={{ APP_ROOT }}
export TREADMILL_DNS_DOMAIN={{ DOMAIN }}
export PEX_ROOT=/tmp/pex
EOF
) >> /root/.bashrc

source /root/.bashrc
