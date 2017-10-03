#!/bin/bash -e

SOURCE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $SOURCE_DIR

if [ "$1" = "help" ]; then
    echo "Usages:"
    echo "./build_binary.sh                                   -- builds binary and rpm in dist/"
    echo "./build_binary.sh <'release-message'> <release-tag> -- builds and release binary on Github"
else
    sudo yum install rpm-build rpmdevtools python-devel -y
    sudo yum groupinstall "Development Tools" -y

    rpmdev-setuptree

    pip install git+https://github.com/thoughtworksinc/pex#egg=pex

    mkdir -p dist
    mkdir -p ~/rpmbuild/SOURCES/treadmill-0.1

    #This needs to go away after ceache kazoo patch is merged and released
    if [ ! -d "kazoo" ]; then
        git clone -b puresasl https://github.com/ceache/kazoo.git
    fi
    echo $2 > treadmill/VERSION.txt

    pex . kazoo -o dist/treadmill -e treadmill.console:run -v --disable-cache
    rm -rf kazoo

    cp dist/treadmill ~/rpmbuild/SOURCES/treadmill-0.1/treadmill
    cp etc/treadmill.spec ~/rpmbuild/SPECS/

    (
        cd ~/rpmbuild/SOURCES/
        tar cvf treadmill-0.1.0.tar.gz treadmill-0.1
    )

    rpmbuild -ba ~/rpmbuild/SPECS/treadmill.spec
    cp ~/rpmbuild/RPMS/noarch/treadmill*rpm dist

    rm -rf ~/rpmbuild

    if [ ! -z "$1" ]; then
        if [ ! -d "/tmp/hub-linux-amd64-2.3.0-pre10" ]; then
            wget -O /tmp/hub-linux-amd64-2.3.0-pre10.tgz http://github.com/github/hub/releases/download/v2.3.0-pre10/hub-linux-amd64-2.3.0-pre10.tgz && tar -xvzf /tmp/hub-linux-amd64-2.3.0-pre10.tgz -C /tmp/
        fi
        /tmp/hub-linux-amd64-2.3.0-pre10/bin/hub release create -p -m "$1" -a dist/treadmill $2
    fi
fi
cd -
