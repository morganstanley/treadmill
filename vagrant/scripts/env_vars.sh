# Configure environment variables.

export TREADMILL_ZOOKEEPER=zookeeper://foo@master:2181
export TREADMILL_CELL=local
export TREADMILL_LDAP=ldap://master:22389
export TREADMILL_LDAP_SUFFIX=dc=local
export TREADMILL_LDAP_PWD=secret
export TREADMILL_LDAP_USER=cn=Manager,dc=local
export LC_ALL=en_US.utf8
export LANG=en_US.utf8

export PATH=$PATH:/opt/s6/bin:/opt/treadmill/bin
