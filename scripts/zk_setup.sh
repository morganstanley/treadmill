cd /home/centos

wget -nc http://apache.claz.org/zookeeper/stable/zookeeper-3.4.9.tar.gz
tar --skip-old-files -xvzf zookeeper-3.4.9.tar.gz
cp -n zookeeper-3.4.9/conf/zoo_sample.cfg zookeeper-3.4.9/conf/zoo.cfg
zookeeper-3.4.9/bin/zkServer.sh start
zookeeper-3.4.9/bin/zkServer.sh status
# env vars
grep -q -F 'source /home/centos/treadmill/scripts/env_vars.sh' ~/.bash_profile || echo 'source /home/centos/treadmill/scripts/env_vars.sh' >> ~/.bash_profile

cd -