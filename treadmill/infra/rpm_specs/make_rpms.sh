#!/bin/bash -e

yum groupinstall -y "Development Tools"
yum install rpmdevtools python2-pip createrepo
rpmdev-setuptree

for file in skalibs-2.4.0.2.tar.gz execline-2.2.0.0.tar.gz s6-2.4.0.0.tar.gz treadmill-pid1-1.0.tar.gz
do
    curl -L https://s3.amazonaws.com/yum_repo_dev/${file} -o rpmbuild/SOURCES/${file}
done

for package in skalibs execline s6 treadmill-pid1
do
    curl -L https://raw.githubusercontent.com/ThoughtWorksInc/treadmill/ldap/treadmill/infra/rpm_specs/${package}.spec -o rpmbuild/SPECS/${package}.spec
    rpmbuild -bb rpmbuild/SPECS/${package}.spec
done

pip install s3cmd
mkdir yum_repo_dev
cd yum_repo_dev
s3cmd sync s3://yum_repo_dev .
cp ../rpmbuild/RPMS/x86_64/*.rpm .
createrepo .
s3cmd sync . s3://yum_repo_dev
s3cmd setacl s3://yum_repo_dev --acl-public --recursive
