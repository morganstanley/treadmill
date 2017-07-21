from urllib import request
from treadmill.infra import connection
import sys

my_ip = request.urlopen(
    'http://ip.42.pl/raw'
).read().decode('utf-8') + '/32'
conn = connection.Connection()
conn.revoke_security_group_ingress(
    CidrIp=my_ip,
    FromPort=22,
    ToPort=22,
    GroupId=sys.argv[1],
    IpProtocol='tcp'
)
