from treadmill.infra import connection
from treadmill.infra import constants


class EC2Object:
    ec2_conn = connection.Connection()
    route53_conn = connection.Connection(
        resource=constants.ROUTE_53
    )

    def __init__(self, name=None, id=None, metadata=None, role=None):
        self._id = id
        self.metadata = metadata
        self.role = role
        self._name = name

    @property
    def id(self):
        return self._extract_id() or self._id

    @property
    def name(self):
        return self._extract_name() or self._name or ''

    def create_tags(self):
        if self.name:
            tags = self._prepare_tag_attributes_for('name')

            if self.role:
                tags = tags + self._prepare_tag_attributes_for('role')

            self.ec2_conn.create_tags(
                Resources=[self.id],
                Tags=tags
            )

    def _prepare_tag_attributes_for(self, attr):
        return [{
            'Key': attr.title(),
            'Value': getattr(self, attr)
        }]

    def _extract_id(self):
        if self.metadata:
            return self.metadata.get(
                self.__class__.__name__.title() + 'Id',
                None
            )

    def _extract_name(self):
        if self._tag_exists():
            return [t['Value']
                    for t in self.metadata['Tags']
                    if t['Key'] == 'Name'][0]

    def _tag_exists(self):
        return self.metadata and self.metadata.get('Tags', None)
