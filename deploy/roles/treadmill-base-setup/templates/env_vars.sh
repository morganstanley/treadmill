export TREADMILL_ZOOKEEPER=zookeeper://foo@{% for instance in instance_facts_master.instances %}{{instance.private_ip_address}}:2181{% if not loop.last %},{% endif %}{% endfor %} 
export TREADMILL_EXE_WHITELIST={{base_dir}}/treadmill/etc/linux.exe.config
export TREADMILL_CELL={{vpc_id}}
export TREADMILL_APPROOT=/tmp/treadmill
export TREADMILL_DNS_DOMAIN={{domain}}
export TREADMILL_LDAP=ldap://{{ freeipa.name|lower }}1.{{ domain }}:1389
export TREADMILL_LDAP_SEARCH_BASE=ou=treadmill,{{ domain | regex_replace('(.*)\\.(.*)', 'dc=\\1,dc=\\2') }}
alias z={{base_dir}}/zookeeper-3.4.9/bin/zkCli.sh
