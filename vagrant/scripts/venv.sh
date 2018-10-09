#/bin/bash

python3 -m venv --without-pip /opt/treadmill

source /opt/treadmill/bin/activate
curl https://bootstrap.pypa.io/get-pip.py | python

pip install numpy
pip install pandas
pip install -r /home/vagrant/treadmill/requirements.txt
pip install -r /home/vagrant/treadmill/test-requirements.txt

cd /home/vagrant/treadmill
./setup.py develop

deactivate
