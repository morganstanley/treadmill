from treadmill.infra import constants, connection
import sys

hosted_zones_to_keep = sys.argv[1:]
route53_conn = connection.Connection(resource=constants.ROUTE_53)
hosted_zones = route53_conn.list_hosted_zones()['HostedZones']
hosted_zone_ids = [hosted_zone['Id'] for hosted_zone in hosted_zones]
hosted_zone_ids = list(set(hosted_zone_ids) - set(hosted_zones_to_keep))
for id in hosted_zone_ids:
    records = route53_conn.list_resource_record_sets(
        HostedZoneId=id
    )['ResourceRecordSets']
    for record in records:
        if record['Type'] not in ["SOA", "NS"]:
            route53_conn.change_resource_record_sets(
                HostedZoneId=id.split('/')[-1],
                ChangeBatch={
                    'Changes': [{
                        'Action': 'DELETE',
                        'ResourceRecordSet': {
                            'Name': record['Name'],
                            'Type': record['Type'],
                            'TTL': record['TTL'],
                            'ResourceRecords': record['ResourceRecords']
                        }
                    }]
                }
            )

    route53_conn.delete_hosted_zone(Id=id)
    print("Deleted" + str(id))
