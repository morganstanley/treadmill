#!/bin/bash -e

echo $1
if [[ "$1" == "help" ]]
then
    echo "Usage:
    ./update_s3_rpm_repo.sh <File1> <File2> ..."
else
    sudo yum -y install awscli createrepo s3cmd
    mkdir -p s3
    (cd s3  && aws s3 sync s3://yum_repo_dev .)

    for file in "$@"
    do
        cp -f $file ./s3
    done

    (
    cd s3
    createrepo .
    aws s3 sync . s3://yum_repo_dev
    s3cmd setacl s3://yum_repo_dev --acl-public --recursive
    )
fi
