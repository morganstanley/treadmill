# install
yum clean all
rpm -ivh https://dl.fedoraproject.org/pub/epel/7/x86_64/e/epel-release-7-10.noarch.rpm
yum -y install python34 python-kerberos git python34-devel

# Configure
{% if HOSTNAME is defined %}
hostnamectl set-hostname "{{ HOSTNAME }}"
{% else %}
hostnamectl set-hostname "{{ NAME }}.{{ DOMAIN }}"
{% endif %}

LDAP_DC=$(echo "{{ DOMAIN }}" | sed -E 's/([a-z]*)\.([a-z]*)/dc=\1,dc=\2/g')
LDAP_URL=ldap://{{ LDAP_HOSTNAME|lower }}:22389
ZK_URL=zookeeper://foo@TreadmillZookeeper1.{{ DOMAIN }}:2181,TreadmillZookeeper2.{{ DOMAIN }}:2181,TreadmillZookeeper3.{{ DOMAIN }}:2181

grep -q -F 'preserve_hostname: true' /etc/cloud/cloud.cfg || echo 'preserve_hostname: true' >> /etc/cloud/cloud.cfg

# Setup environment vars
(
cat <<EOF
export TREADMILL_ZOOKEEPER=$ZK_URL
export TREADMILL_LDAP=$LDAP_URL
export TREADMILL_LDAP_SUFFIX=${LDAP_DC}
export TREADMILL_CELL={{ SUBNET_ID }}
export TREADMILL_APPROOT={{ APP_ROOT }}
export TREADMILL_DNS_DOMAIN={{ DOMAIN }}
export TREADMILL=/opt/treadmill
export PEX_ROOT=/tmp/pex
export PATH=$PATH:/opt/s6/bin:/opt/treadmill/bin
EOF
) >> /etc/profile.d/treadmill_profile.sh

source /etc/profile.d/treadmill_profile.sh
