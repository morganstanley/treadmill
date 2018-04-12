#!/bin/sh

function usage {
    echo "Usage: " $(basename $0)
    echo "  -b <s3 bucket path>"
    echo "  -w <wheel dir>                   : default ~/wheels"
    echo "  -p <aws profile>                 : [optional]"
    exit -1
}

while getopts "w:b:p:" OPT; do
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

if [ -z $BUCKET ]; then
    usage
fi

echo "Wheels      : $WHEELS_DIR"
echo "AWS profile : $PROFILE"
echo "Bucket      : $BUCKET"

aws --profile $PROFILE \
    s3 sync $WHEELS_DIR $BUCKET --delete
