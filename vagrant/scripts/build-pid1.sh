#/bin/bash

cd $(mktemp -d)

for f in $(ls /home/vagrant/treadmill-pid1/); do
    ln -s /home/vagrant/treadmill-pid1/$f
done

make
install -Dv pid1 /opt/treadmill-pid1/bin/pid1

