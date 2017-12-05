#!/bin/bash -e

SCRIPT_NAME=${0##*/}
SCRIPT_DIR=${0%/${SCRIPT_NAME}}

BASE_DIR=$(realpath "${SCRIPT_DIR}/../")

if [ "$1" = "help" ]; then
    echo "Usages:"
    echo "${SCRIPT_NAME}                                   -- builds binary and rpm in dist/"
    echo "${SCRIPT_NAME} <'release-message'> <release-tag> -- builds and release binary on Github"
else
    set -e
    set -x

    sudo yum install rpm-build rpmdevtools python-devel -y
    sudo yum groupinstall "Development Tools" -y

    rpmdev-setuptree

    mkdir -vp "${BASE_DIR}/rpmbuild/SOURCES/treadmill-0.1"

    pushd "${BASE_DIR}"

    echo $2 > /treadmill/VERSION.txt

    cp -v dist/treadmill "${BASE_DIR}/rpmbuild/SOURCES/treadmill-0.1/treadmill"
    cp -v etc/treadmill.spec "${BASE_DIR}/rpmbuild/SPECS/"

    (
        pushd "${BASE_DIR}/rpmbuild/SOURCES/"
        tar cvf treadmill-0.1.0.tar.gz treadmill-0.1
    )

    rpmbuild -ba "${BASE_DIR}/rpmbuild/SPECS/treadmill.spec"
    cp -v "${BASE_DIR}/rpmbuild/RPMS/noarch/treadmill*rpm" ${BASE_DIR}/dist/

    rm -rf "${BASE_DIR}/rpmbuild"

    if [ ! -z "$1" ]; then
        if [ ! -d "/tmp/hub-linux-amd64-2.3.0-pre10" ]; then
            wget -O /tmp/hub-linux-amd64-2.3.0-pre10.tgz http://github.com/github/hub/releases/download/v2.3.0-pre10/hub-linux-amd64-2.3.0-pre10.tgz && tar -xvzf /tmp/hub-linux-amd64-2.3.0-pre10.tgz -C /tmp/
        fi
        /tmp/hub-linux-amd64-2.3.0-pre10/bin/hub release create -p -m "$1" -a "${BASE_DIR}/dist/treadmill" $2
    fi
fi
