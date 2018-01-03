#!/bin/bash

set -e
set -x

SCRIPT_NAME=${0##*/}
SCRIPT_DIR=${0%/${SCRIPT_NAME}}

BASE_DIR=$(realpath "${SCRIPT_DIR}/../")
WHEELS_DIR=$(realpath "${BASE_DIR}/wheels/")

CAN_BUILD_WHEELS="
    aniso8601
    backports.ssl_match_hostname
    blinker
    dateutils
    flask
    flask-restfull
    ipaddress
    iscpy
    itsdangerous
    markupsafe
    netifaces
    parse
    pluggy
    polling
    prettytable
    psutil
    pure-sasl
    pycparser
    pykerberos
    pyyaml
    requests-unixsocket
    simplejson
    tornado
    twisted
    tzlocal
    urllib_kerberos
    wrapt
"
CAN_BUILD_WHEELS=$(echo ${CAN_BUILD_WHEELS} | sed 's/[ ]\+/,/g')

echo "Caching all the wheels..."
mkdir -vp "${WHEELS_DIR}"
pip ${PIP_OPTIONS} wheel \
    -r "${BASE_DIR}/requirements.txt" \
    -r "${BASE_DIR}/test-requirements.txt" \
    -w "${WHEELS_DIR}" \
    --only-binary :all: \
    --no-binary ${CAN_BUILD_WHEELS}

echo "Patching the wheels..."
for WHEEL in  $(find "${WHEELS_DIR}" -name "*manylinux1*")
do
    mv -v ${WHEEL} $(echo ${WHEEL} | sed s/manylinux1/linux/)
done
