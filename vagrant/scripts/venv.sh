#/bin/bash

python3 -m venv --without-pip /opt/treadmill

source /opt/treadmill/bin/activate
curl https://bootstrap.pypa.io/get-pip.py | python

pip install --only-binary all -r /home/vagrant/treadmill/requirements.txt
pip install --only-binary all pbr==1.10.0
pip install --only-binary all -r /home/vagrant/treadmill/test-requirements.txt
pip install --only-binary all pbr==2.0.0

cd /home/vagrant/treadmill
./setup.py develop

deactivate
