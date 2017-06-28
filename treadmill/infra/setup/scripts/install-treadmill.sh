# Add treadmld user
id -u treadmld &>/dev/null || useradd treadmld

# Install PID1
if [ ! -e /etc/yum.repos.d/treadmill.repo ]; then
    curl -L https://s3.amazonaws.com/yum_repo_dev/treadmill.repo -o /etc/yum.repos.d/treadmill.repo
fi
yum install treadmill-pid1 --nogpgcheck -y

# Install S6
if [ ! -e /etc/yum.repos.d/treadmill.repo ]; then
    curl -L https://s3.amazonaws.com/yum_repo_dev/treadmill.repo -o /etc/yum.repos.d/treadmill.repo
fi
yum install s6 --nogpgcheck -y

# Install treadmill
curl -L "https://github.com/ThoughtWorksInc/treadmill/releases/download/{{ TREADMILL_RELEASE }}/treadmill" -o /bin/treadmill
chmod +x /bin/treadmill
