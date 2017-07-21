(
cat <<EOF
[Unit]
Description=Treadmill node services
After=network.target

[Service]
User=root
Group=root
SyslogIdentifier=treadmill
ExecStartPre=/bin/mount --make-rprivate /
ExecStart={{ APP_ROOT }}/treadmill/bin/run.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
) > /etc/systemd/system/treadmill-node.service

treadmill --outfmt yaml admin ldap cell configure local > {{ APP_ROOT }}/cell_conf.yml

systemctl start treadmill-node.service

treadmill admin install \
    --install-dir {{ APP_ROOT }}/treadmill-node \
    --install-dir {{ APP_ROOT }}/treadmill \
    --config {{ APP_ROOT }}/cell_conf.yml \
    node
