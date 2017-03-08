export TREADMILL_ZOOKEEPER={% for instance in instance_facts_master.instances %}zookeeper://foo@{{instance.public_ip_address}}:2181,{% endfor %} 
export TREADMILL_EXE_WHITELIST={{base_dir}}/treadmill/etc/linux.exe.config
export TREADMILL_CELL=localhost.localdomain
export TREADMILL_APPROOT=/tmp/treadmill
alias z={{base_dir}}/zookeeper-3.4.9/bin/zkCli.sh