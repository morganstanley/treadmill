import unittest
import mock
from treadmill.infra.utils import hosted_zones


class HostedZoneTest(unittest.TestCase):
    @mock.patch('treadmill.infra.connection.Connection')
    def test_delete_record(self, connectionMock):
        conn = connectionMock()
        hosted_zones.route53_conn = conn
        record = {
            'Name': 'foo',
            'Type': 'bar',
            'TTL': '100',
            'ResourceRecords': 'somerecords'
        }

        hosted_zones.delete_record('/hostedzone/abc', record)

        conn.change_resource_record_sets.assert_called_once_with(
            HostedZoneId='abc',
            ChangeBatch={
                'Changes': [{
                    'Action': 'DELETE',
                    'ResourceRecordSet': {
                        'Name': 'foo',
                        'Type': 'bar',
                        'TTL': '100',
                        'ResourceRecords': 'somerecords'
                    }
                }]
            }
        )

    @mock.patch('treadmill.infra.connection.Connection')
    def test_delete_obsolete(self, connectionMock):
        conn = connectionMock()
        hosted_zones.route53_conn = conn
        expected_hosted_zones = [
            {'Id': '/hostedzone/1'},
            {'Id': '/hostedzone/2'},
            {'Id': '/hostedzone/3'}
        ]
        conn.list_hosted_zones = mock.Mock(
            return_value={'HostedZones': expected_hosted_zones}
        )
        hosted_zones.delete_obsolete(('1', '2'))
        conn.delete_hosted_zone.assert_called_once_with(
            Id='/hostedzone/3'
        )
