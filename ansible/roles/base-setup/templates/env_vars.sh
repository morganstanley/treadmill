export TREADMILL_ZOOKEEPER=zookeeper://foo@{% for instance in instance_facts_master.instances %}{{instance.private_ip_address}}:2181{% if not loop.last %},{% endif %}{% endfor %} 
export TREADMILL_EXE_WHITELIST={{base_dir}}/treadmill/etc/linux.exe.config
export TREADMILL_CELL=localhost.localdomain
export TREADMILL_APPROOT=/tmp/treadmill
alias z={{base_dir}}/zookeeper-3.4.9/bin/zkCli.sh