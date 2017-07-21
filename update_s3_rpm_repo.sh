echo $1
if [[ "$1" == "help" ]]
then
    echo "Usage:
    ./update_s3_rpm_repo.sh <File1> <File2> ..."
else
    yum -y install awscli createrepo s3cmd
    mkdir s3
    cd s3

    aws s3 sync s3://yum_repo_dev .
    for file in "$@"
    do
        cp -f $file ./
    done

    createrepo .
    aws s3 sync . s3://yum_repo_dev
    s3cmd setacl s3://yum_repo_dev --acl-public --recursive
fi
