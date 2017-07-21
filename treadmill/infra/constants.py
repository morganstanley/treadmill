ROUTE_53 = 'route53'
EC2 = 'ec2'
ROUTE_53_RECORD_SET_TTL = 3600
IPA_ROUTE_53_RECORD_SET_TTL = 86400
REVERSE_DNS_TLD = 'in-addr.arpa'
ATTACHMENT_INSTANCE_ID = 'attachment.instance-id'
ATTACHMENT_VPC_ID = 'attachment.vpc-id'
DESTINATION_CIDR_BLOCK = '0.0.0.0/0'
IPA_HOSTNAME = 'treadmillipa'
MASTER_INSTANCES_COUNT = 3
TREADMILL_CELL_SUBNET_NAME = 'TreadmillCell'
INSTANCE_TYPES = {
    'EC2': {
        'micro': 't2.micro',
        'small': 't2.small',
        'medium': 't2.medium',
        'large': 't2.large',
        'xlarge': 't2.xlarge',
        '2xlarge': 't2.2xlarge',

    }
}
ROLES = {
    'MASTER': 'MASTER',
    'NODE': 'NODE',
    'LDAP': 'LDAP',
    'IPA': 'IPA',
    'ZOOKEEPER': 'ZOOKEEPER',
    'DEFAULT': 'DEFAULT'
}
