#!/bin/sh

function usage {
    echo "Usage: " $(basename $0)
    echo "  -b <s3 bucket path>"
    echo "  -d <destination>"
    echo "  -w <wheel dir>                   : default <install_dir>/wheels"
    echo "  -p <aws profile>                 : [optional]"
    exit -1
}

while getopts "d:w:b:p:" OPT; do
    case "${OPT}" in
        w)
            WHEELS_DIR=${OPTARG}
            ;;
        d)
            INSTALL_DIR=${OPTARG}
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

if [ -z $BUCKET ]; then
    usage
fi

if [ -z $INSTALL_DIR ]; then
    usage
fi

if [ "$WHEELS_DIR" == "" ]; then
    WHEELS_DIR=$INSTALL_DIR/wheels
fi

if [ "$PROFILE" == "" ]; then
    PROFILE=default
fi

echo "Install dir      : $INSTALL_DIR"
echo "Wheels cache     : $WHEELS_DIR"
echo "AWS profile      : $PROFILE"
echo "Bucket           : $BUCKET"

virtualenv-3 $INSTALL_DIR
source $INSTALL_DIR/bin/activate
pip install -U setuptools pip

mkdir -p $WHEELS_DIR

aws --profile $PROFILE \
    s3 sync $BUCKET $WHEELS_DIR --delete

pip install -f $WHEELS_DIR    \
    --only-binary             \
    --no-cache-dir            \
    --no-index                \
    $*
