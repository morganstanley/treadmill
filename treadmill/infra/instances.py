from treadmill.infra import connection
from treadmill.infra import ec2object
from treadmill.infra import constants
from treadmill.api import ipa

from datetime import datetime
from functools import reduce
import logging

import polling

_LOGGER = logging.getLogger(__name__)


class Instance(ec2object.EC2Object):
    def __init__(self, name=None, id=None, metadata=None, role=None):
        super().__init__(
            id=id,
            name=name,
            metadata=metadata,
            role=role
        )
        self._running_status = None
        self.private_ip = self._get_private_ip()

    def running_status(self, refresh=False):
        if refresh or not self._running_status:
            _status = self.ec2_conn.describe_instance_status(
                InstanceIds=[self.metadata['InstanceId']]
            )['InstanceStatuses']
            if _status:
                self._running_status = _status[0]['InstanceStatus'][
                    'Details'
                ][0]['Status']
            else:
                self._running_status = self.metadata['State']['Name']

        return self._running_status

    @property
    def hostname(self):
        return self.name

    @property
    def subnet_id(self):
        if self.metadata:
            return self.metadata.get('SubnetId', None)

    def _get_private_ip(self):
        return self.metadata.get(
            'PrivateIpAddress',
            ''
        ) if self.metadata else ''

    def _reverse_dns_record_attrs(self):
        return [
            self._reverse_dns_record_name(),
            'PTR',
            self._forward_dns_name()
        ]

    def _forward_dns_name(self):
        return self.name.lower(
        ) + '.' + connection.Connection.context.domain + '.'

    def _forward_dns_record_attrs(self):
        return [
            self._forward_dns_name(),
            'A',
            self.private_ip
        ]

    def _reverse_dns_record_name(self):
        ip_octets = self.private_ip.split('.')
        ip_octets.reverse()
        ip_octets.append(constants.REVERSE_DNS_TLD)

        return '.'.join(ip_octets)


class Instances:
    def __init__(self, instances):
        self.instances = instances
        self.volume_ids = []
        self.ec2_conn = connection.Connection()

    @property
    def ids(self):
        return [i.id for i in self.instances]

    @classmethod
    def load_json(cls, ids=None, filters=None):
        """Fetch instance details"""
        conn = connection.Connection()

        if ids:
            response = conn.describe_instances(
                InstanceIds=ids
            )['Reservations']
        elif filters:
            response = conn.describe_instances(
                Filters=filters
            )['Reservations']
        else:
            return []

        return sum([r['Instances'] for r in response], [])

    @classmethod
    def get(cls, ids=None, filters=None):
        json = Instances.load_json(ids=ids, filters=filters)
        return Instances(
            instances=[Instance(
                id=j['InstanceId'],
                metadata=j
            ) for j in json]
        )

    @classmethod
    def get_by_roles(cls, vpc_id, roles):
        _instances = cls.get(
            filters=[
                {
                    'Name': 'vpc-id',
                    'Values': [vpc_id]
                },
                {
                    'Name': 'tag-key',
                    'Values': ['Role']
                },
                {
                    'Name': 'tag-value',
                    'Values': roles
                }
            ]
        )
        return _instances

    @classmethod
    def get_hostnames_by_roles(cls, vpc_id, roles):
        _instances = cls.get_by_roles(
            vpc_id=vpc_id,
            roles=roles
        ).instances

        _hostnames = {}
        for _i in _instances:
            if _hostnames.get(_i.role):
                _hostnames[_i.role] += ',' + _i.hostname
            else:
                _hostnames[_i.role] = _i.hostname

        return _hostnames

    @classmethod
    def create(
            cls,
            name,
            key_name,
            count,
            image,
            instance_type,
            subnet_id,
            secgroup_ids,
            user_data,
            role
    ):
        conn = connection.Connection()
        _instances = conn.run_instances(
            ImageId=Instances.get_ami_id(image),
            MinCount=count,
            MaxCount=count,
            InstanceType=instance_type,
            KeyName=key_name,
            UserData=user_data,
            NetworkInterfaces=[{
                'DeviceIndex': 0,
                'SubnetId': subnet_id,
                'Groups': secgroup_ids,
                'AssociatePublicIpAddress': True
            }],
            IamInstanceProfile={
                'Name': constants.IPA_EC2_IAM_ROLE
            } if role == 'IPA' else {}
        )

        _ids = [i['InstanceId'] for i in _instances['Instances']]
        _instances_json = Instances.load_json(ids=_ids)

        _instances = []
        for i in _instances_json:
            _instance = Instance(
                id=i['InstanceId'],
                name=name,
                metadata=i,
                role=role
            )
            _instance.create_tags()
            _instances.append(_instance)

        return Instances(instances=_instances)

    def load_volume_ids(self):
        if not self.volume_ids:
            volumes = self.ec2_conn.describe_volumes(
                Filters=[{
                    'Name': constants.ATTACHMENT_INSTANCE_ID,
                    'Values': self.ids
                }]
            )
            self.volume_ids = [v['VolumeId'] for v in volumes['Volumes']]

    def terminate(self):
        if self.ids:
            self.ec2_conn.terminate_instances(
                InstanceIds=self.ids
            )
            self._wait_for_termination()

        self.load_volume_ids()
        if self.volume_ids:
            self.delete_volumes()

        self._delete_host_from_ipa()

    def _delete_host_from_ipa(self):
        _api = ipa.API()
        for _i in self.instances:
            if _i.role != constants.ROLES['IPA']:
                try:
                    _api.delete_host(hostname=_i.hostname.lower())
                except AssertionError as e:
                    _LOGGER.warn(
                        'Couldn\'t delete host ' + _i.hostname + ' from ipa. ',
                        e
                    )

    def delete_volumes(self):
        for volume_id in self.volume_ids:
            self.ec2_conn.delete_volume(VolumeId=volume_id)

    def _wait_for_termination(self):
        if len(self.ids) == 0:
            return

        def is_terminated(res):
            _LOGGER.info("\nWaiting for instances termination...")
            _LOGGER.info("Current states:")
            instance_data = [
                status['InstanceId'] + ": " + status['InstanceState']['Name']
                for status in res['InstanceStatuses']
            ]
            _LOGGER.info("\n".join(instance_data))

            instance_statuses = list(set(
                [
                    status['InstanceState']['Name']
                    for status in res['InstanceStatuses']
                ]
            ))

            status_len = len(instance_statuses)
            return (
                status_len == 0
            ) or (
                status_len == 1 and instance_statuses[0] == 'terminated'
            )

        if polling.poll(
            lambda: self.ec2_conn.describe_instance_status(
                InstanceIds=self.ids,
                IncludeAllInstances=True
            ),
            check_success=is_terminated,
            step=10,
            timeout=300
        ):
            return

    @classmethod
    def get_ami_id(cls, image):
        conn = connection.Connection()
        images = conn.describe_images(
            Filters=[
                {'Name': 'name', 'Values': [image + '*']},
                {'Name': 'owner-id', 'Values': ['309956199498']},
                {'Name': 'image-type', 'Values': ['machine']}
            ],
        )['Images']

        def get_time(str):
            return datetime.strptime(str, '%Y-%m-%dT%H:%M:%S.%fZ')

        return reduce(
            (
                lambda x, y:
                x
                if get_time(x['CreationDate']) > get_time(y['CreationDate'])
                else y
            ),
            images
        )['ImageId']
