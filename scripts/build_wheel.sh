#!/bin/sh

set -e

function usage {
    echo "Usage: " $(basename $0)
    echo "  -b <s3 bucket path>"
    echo "  -w <wheel dir>                   : default <install_dir>/wheels"
    echo "  -p <aws profile>                 : [optional]"
    exit -1
}

while getopts "d:w:b:p:" OPT; do
    case "${OPT}" in
        w)
            WHEELS_DIR=${OPTARG}
            ;;
        b)
            BUCKET=${OPTARG}
            ;;
        p)
            PROFILE=${OPTARG}
            ;;
    esac
done
shift $((OPTIND-1))

if [ "$WHEELS_DIR" == "" ]; then
    WHEELS_DIR=~/wheels/
fi

if [ "$PROFILE" == "" ]; then
    PROFILE=default
fi

echo "Wheels cache     : $WHEELS_DIR"
echo "AWS profile      : $PROFILE"
echo "Bucket           : $BUCKET"

if [ ! -z $BUCKET ]; then
    aws --profile $PROFILE \
        s3 sync $BUCKET $WHEELS_DIR --delete
fi

# All requirements should be in the wheel cache, disable pypi.
pip ${PIP_OPTIONS} wheel \
    --no-index         \
    -f "${WHEELS_DIR}" \
    -w "${WHEELS_DIR}" \
    .
