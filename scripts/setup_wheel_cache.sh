#!/bin/sh

set -e

SCRIPT_NAME=${0##*/}
SCRIPT_DIR=${0%/${SCRIPT_NAME}}

BASE_DIR=$(realpath "${SCRIPT_DIR}/../")

while getopts "w:" OPT; do
    case "${OPT}" in
        w)
            WHEELS_DIR=${OPTARG}
            ;;
    esac
done
shift $((OPTIND-1))

if [ "$WHEELS_DIR" = "" ]; then
    WHEELS_DIR=~/wheels/
fi

CAN_BUILD_WHEELS="
    aniso8601
    backports.ssl_match_hostname
    blinker
    dateutils
    gssapi
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
    -r requirements.txt \
    -r test-requirements.txt \
    -f "${WHEELS_DIR}" \
    -w "${WHEELS_DIR}" \
    --only-binary :all: \
    --no-binary ${CAN_BUILD_WHEELS}

echo "Patching the wheels..."
for WHEEL in $(find "${WHEELS_DIR}" -name "*manylinux1*")
do
    mv -v ${WHEEL} $(echo ${WHEEL} | sed s/manylinux1/linux/)
done

# All requirements should be downloaded from requirements.txt, disable
# pypi
pip ${PIP_OPTIONS} wheel \
    --no-index         \
    -f "${WHEELS_DIR}" \
    -w "${WHEELS_DIR}" \
    .

cd ${WHEELS_DIR}
for f in `ls *.whl`; do echo "<a href=\"$f\">$f</a>"; done > index.html
cd -
