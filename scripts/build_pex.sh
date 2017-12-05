#!/bin/bash

set -e
set -x

SCRIPT_NAME=${0##*/}
SCRIPT_DIR=${0%/${SCRIPT_NAME}}

BASE_DIR=$(realpath "${SCRIPT_DIR}/../")
WHEELS_DIR=$(realpath "${BASE_DIR}/wheels/")

if [ ! -d "${WHEELS_DIR}" ]; then
    echo "Cache wheels first!"
    exit 1
fi

pushd "${BASE_DIR}"

PEX="$(which pex)"
if [ $? -ne 0 ]; then
    echo "Install pex! first"
    exit 1
fi

EGG="${BASE_DIR}/dist/*.egg"
if [ ! -e ${EGG} ]; then
    python ./setup.py -vvv \
        build \
            --build-base ../build \
        bdist_egg

    EGG="${BASE_DIR}/dist/*.egg"
fi
if [ ! -e ${EGG} ]; then
    echo "Build failed or dist dirty!"
    exit 1
fi

${PEX} -vvv ${EGG} \
    -o dist/treadmill \
    -c treadmill \
    --disable-cache \
    --no-pypi \
    --no-build \
    --repo ${WHEELS_DIR} \
    -r requirements_pex.txt 
