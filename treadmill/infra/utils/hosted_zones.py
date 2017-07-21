from treadmill.infra import constants, connection

route53_conn = connection.Connection(resource=constants.ROUTE_53)


def delete_obsolete(zone_ids_to_keep):
    hosted_zones = route53_conn.list_hosted_zones()['HostedZones']
    all_zone_ids = [hosted_zone['Id'] for hosted_zone in hosted_zones]
    zone_ids_to_keep = ['/hostedzone/' + id for id in zone_ids_to_keep]
    zone_ids_to_delete = list(set(all_zone_ids) - set(zone_ids_to_keep))

    for id in zone_ids_to_delete:
        records = route53_conn.list_resource_record_sets(
            HostedZoneId=id
        )['ResourceRecordSets']
        for record in records:
            if record['Type'] not in ["SOA", "NS"]:
                delete_record(id, record)

        route53_conn.delete_hosted_zone(Id=id)


def delete_record(zone_id, record):
    route53_conn.change_resource_record_sets(
        HostedZoneId=zone_id.split('/')[-1],
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
