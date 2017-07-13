from treadmill.infra import connection
from treadmill.infra import constants


class EC2Object:
    def __init__(self, name=None, id=None, metadata=None):
        self.id = id
        self.name = name
        self.metadata = metadata
        self.ec2_conn = connection.Connection()
        self.route53_conn = connection.Connection(
            resource=constants.ROUTE_53
        )

        if self.metadata and self.metadata.get('Tags', None):
            self.name = [t['Value']
                         for t in self.metadata['Tags']
                         if t['Key'] == 'Name'][0]

    def create_tags(self):
        self.ec2_conn.create_tags(
            Resources=[self.id],
            Tags=[{
                'Key': 'Name',
                'Value': self.name
            }]
        )
