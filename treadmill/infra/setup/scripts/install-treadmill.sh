if [ ! -e /etc/yum.repos.d/treadmill.repo ]; then
    curl -L https://s3.amazonaws.com/yum_repo_dev/treadmill.repo -o /etc/yum.repos.d/treadmill.repo
fi

# Install S6 and pid1
yum install s6 execline treadmill-pid1 --nogpgcheck -y

# Install treadmill
mkdir -p /opt/treadmill/bin
curl -L "https://github.com/ThoughtWorksInc/treadmill/releases/download/{{ TREADMILL_RELEASE }}/treadmill" -o /opt/treadmill/bin/treadmill
chmod +x /opt/treadmill/bin/treadmill
