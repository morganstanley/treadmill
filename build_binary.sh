#!/bin/bash -e

sudo yum install rpm-build rpmdevtools python-devel -y
sudo yum groupinstall "Development Tools" -y

rpmdev-setuptree

pip install git+https://github.com/thoughtworksinc/pex#egg=pex

mkdir -p dist
mkdir -p ~/rpmbuild/SOURCES/treadmill-0.1

pex . -o dist/treadmill.pex -e treadmill.console:run -v

cp dist/treadmill.pex ~/rpmbuild/SOURCES/treadmill-0.1/treadmill
cp etc/treadmill.spec ~/rpmbuild/SPECS/

cd ~/rpmbuild/SOURCES/
tar cvf treadmill-0.1.0.tar.gz treadmill-0.1
cd -

rpmbuild -ba ~/rpmbuild/SPECS/treadmill.spec
cp ~/rpmbuild/RPMS/noarch/treadmill*rpm dist

rm -rf ~/rpmbuild
