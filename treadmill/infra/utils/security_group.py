from urllib import request
from treadmill.infra import connection

my_ip = request.urlopen(
    'http://ip.42.pl/raw'
).read().decode('utf-8') + '/32'


def enable(port, group_id, protocol='tcp'):
    port = int(port)
    conn = connection.Connection()
    conn.authorize_security_group_ingress(
        CidrIp=my_ip,
        FromPort=port,
        ToPort=port,
        GroupId=group_id,
        IpProtocol=protocol
    )


def disable(port, group_id, protocol='tcp'):
    port = int(port)
    conn = connection.Connection()
    conn.revoke_security_group_ingress(
        CidrIp=my_ip,
        FromPort=port,
        ToPort=port,
        GroupId=group_id,
        IpProtocol=protocol
    )
