"""Compute billing volumes for the allocations in a cell."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from datetime import datetime
import logging
import os
import re
import time
import traceback

import numpy as np
import pandas as pd

from treadmill import admin  # pylint: disable=E0611
from treadmill import context  # pylint: disable=E0611

from treadmill.ms import proiddb


# Utility constants for loading reports
TREADMILL_DATA = '/v/region/local/appl/cloud/treadmill/data'
INTERVAL_DIR = os.path.join(TREADMILL_DATA, '{env}/state_reports/{cell}')
INTERVAL_FILENAME = re.compile(''.join([
    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'
    r'_(servers|allocations|apps)\.csv\.bz2$'
]))
DAILY_DIR = os.path.join(TREADMILL_DATA, 'global-{env}/billing/daily/{cell}')
DAILY_FILENAME = re.compile(r'\d{4}-\d{2}-\d{2}.csv')
MONTHLY_DIR = os.path.join(TREADMILL_DATA, 'global-{env}/billing/monthly')

# Constants for the billing algorithm
TIERS = {
    'spot': 1,
    'fluid': 4,
    'solid': 5
}
ALPHA = 0.2
DISCOUNT = 1 - ALPHA
TREADMILL_SYSTEMS = [43626]
UNUSED_VOLUME_SYSTEMID = 2783  # Unused volume gets assigned to this system id
UNUSED_VOLUME_TENANT = 'grn:/ms/ei/unix/os/Linux'

# Following values are part of contract with billing feed consumers
ID_ALLOC_VOL = -1
ID_CELL_VOL = -2
ID_CELL_MEM = -10
ID_CELL_CPU = -11
ID_CELL_DISK = -12
ID_UNKNOWN_TENANT = -999
CELL_STATS_LABEL = '[cell statistics]'
TOTAL_CELL_MEM = '[total cell mem]'
TOTAL_CELL_CPU = '[total cell cpu]'
TOTAL_CELL_DISK = '[total cell disk]'
TOTAL_CELL_VOLUME = '[total cell volume]'
TOTAL_ALLOC_VOLUME = '[total allocated volume]'
UNUSED_VOLUME_LABEL = '[unused capacity]'
PRIVATE_PARTITION_LABEL = '[private partition]'
PRIVATE_PARTITION_DF = pd.DataFrame([
    (PRIVATE_PARTITION_LABEL, 0)  # To be filled in as needed
], columns=('allocation', 'volume'))

# Utility constants for manipulating DataFrames
DIMENSIONS = ['mem', 'cpu', 'disk']
CAPACITY_AGGREGATORS = {dim: 'sum' for dim in DIMENSIONS}
SERVER_COLUMNS = ['partition', 'name'] + DIMENSIONS
SERVER_AGGREGATORS = {
    'mem': 'sum',
    'cpu': 'sum',
    'disk': 'sum',
    'name': 'count'
}
ALLOCS_COLUMNS = ['partition', 'name'] + DIMENSIONS
APPS_COLUMNS = ['partition', 'instance', 'allocation'] + DIMENSIONS
VOLUME_COLUMNS = ['volume'] + DIMENSIONS
VOLUME_AGGREGATORS = {dim: 'sum' for dim in VOLUME_COLUMNS}

NO_PARTITION = {
    'tier': TIERS['solid'],
    'private': False,
    'systems': []
}

DAILY_REPORT_PERIOD = 60 * 60 * 24

# Firmwide Directory to query mailgroups for personal containers
FWD_HOST = 'fwldap-prod.ms.com:389'
FWD_BASE = 'ou=Groups,o=Morgan Stanley'


INTERACTIVE = False
_LOGGER = logging.getLogger(__name__)


def volumes_for_period(
        start_dt, end_dt, cell_name, env='prod',
        adjust=True, reports=None):
    """Prepare report of volume per allocation for given period."""
    timing_start = time.time()

    if reports is None:
        reports = list_interval_reports(start_dt, end_dt, cell_name, env)

    partitions = get_cell_partitions(cell_name)

    volumes, capacities = _compute_volumes_for_period(
        partitions, reports, cell_name, env
    )

    _LOGGER.info('Adding allocation information')

    _add_alloc_tenant(volumes)
    _add_alloc_system_env(partitions, volumes)

    # Get total capacity and volume per partition
    part_capacities = capacities.groupby('partition')
    total_part_volume = part_capacities['volume'].first()

    # Get total allocation volume for non-private partitions
    total_alloc_volume = volumes.loc[volumes['system'] > 0]\
        .groupby('partition')['volume']\
        .sum()\
        .loc[lambda vols: vols.index.map(  # index is the partition name
            lambda partition: not partitions.get(partition, NO_PARTITION)[
                'private']
        )]

    if adjust:
        # Adjust volumes to fit partition by discounting or shredding
        _adjust_volumes(volumes, total_alloc_volume, total_part_volume)

    _add_partition_stats(
        volumes, total_alloc_volume, total_part_volume, part_capacities
    )

    volumes['period_start'] = start_dt.strftime('%Y-%m-%d')
    volumes['period_end'] = end_dt.strftime('%Y-%m-%d')

    result = volumes.rename(columns={
        # Rename to maintain compatibility with Treadmill 2 billing feed
        'partition': 'cell',
        'system': 'eonid'
    })[[
        'period_start', 'period_end', 'cell',
        'eonid', 'env',
        'tenant', 'allocation',
        'volume'
    ]].sort_values(
        ['cell', 'eonid', 'volume'], ascending=[True, True, False]
    ).reset_index(drop=True)

    result['cell'] = cell_name + '/' + result['cell']

    _LOGGER.info('%d seconds', (time.time() - timing_start))
    return result


def combine_periods(start, end, cell_name, env='prod', adjust=True):
    """Combine billing reports for multiple periods.

    In theory, volumes_for_period can compute volumes for any given period.
    In practice, we use it to compute daily feeds, and combine these feeds
    into monthly feeds (billing months run from the 15th to the 15th).
    """
    timing_start = time.time()

    reports = list_daily_reports(start, end, cell_name, env)
    num_reports = len(reports)
    if not num_reports:
        _LOGGER.warning(
            'No daily reports found between %s and %s for cell %s in %s',
            start.strftime('%Y-%m-%d'),
            end.strftime('%Y-%m-%d'),
            cell_name, env
        )
        return

    volume_frames = []
    report_period = 0
    for i, report in reports.iterrows():
        report_date = report['date'].strftime('%Y-%m-%d')
        _progress(i, num_reports, report_date)

        try:  # We don't want a glitch to stop the entire endeavour
            volumes = pd.read_csv(os.path.join(
                DAILY_DIR.format(cell=cell_name, env=env),
                report['filename']
            ))

            volumes['volume'] *= report['dt']
            volume_frames.append(volumes)

            report_period += report['dt']
        except Exception:  # really catch everything pylint: disable=W0703
            _progress_complete()
            _LOGGER.error(
                'Failed to load %s report %s',
                cell_name, report_date
            )
            _LOGGER.error(traceback.format_exc())

    _progress_complete()

    volumes = pd.concat(volume_frames, ignore_index=True, copy=False)
    period_start = volumes['period_start'].min()
    period_end = volumes['period_end'].max()

    # Convert all volumes to node-period units by summing the respective volume
    # from each day and dividing by the report period
    pk_columns = ['cell', 'eonid', 'env', 'tenant', 'allocation']
    # Fill NaN fields, otherwise stats rows get ignored by groupby
    volumes = volumes[pk_columns + ['volume']].fillna('')
    volumes = volumes.groupby(pk_columns).sum().reset_index().rename(columns={
        # Rename back to Treadmill 3 terminology for _adjust_volumes
        'cell': 'partition',
        'eonid': 'system'
    })
    volumes['volume'] /= report_period

    if adjust:
        # Adjust volumes to fit partition by discounting or shredding
        total_alloc_volume = volumes.loc[
            volumes['system'] == ID_ALLOC_VOL, ['partition', 'volume']
        ].set_index('partition')['volume']
        total_part_volume = volumes.loc[
            volumes['system'] == ID_CELL_VOL, ['partition', 'volume']
        ].set_index('partition')['volume']
        _adjust_volumes(volumes, total_alloc_volume, total_part_volume)

    volumes['period_start'] = period_start
    volumes['period_end'] = period_end

    result = volumes.rename(columns={
        # Rename to maintain compatibility with Treadmill 2 billing feed
        'partition': 'cell',
        'system': 'eonid'
    })[[
        'period_start', 'period_end', 'cell',
        'eonid', 'env',
        'tenant', 'allocation',
        'volume'
    ]].sort_values(
        ['cell', 'eonid', 'volume'], ascending=[True, True, False]
    ).reset_index(drop=True)

    _LOGGER.info('%d seconds', (time.time() - timing_start))
    return result


def concatenate_reports(month, env='prod'):
    """Concatenate cell reports into a single Treadmill billing feed."""
    reports = list_monthly_reports(month, env)
    _LOGGER.info('Cells: %s', ' '.join(report[0] for report in reports))
    report_frames = []
    period = None
    for cell, filename in reports:
        report = pd.read_csv(filename)
        report_period = tuple(report.loc[0, ['period_start', 'period_end']])
        if period is None:
            period = report_period
        elif report_period != period:
            _LOGGER.warning(
                'Cell %s has unusual period for month %s: %r',
                cell, month, report_period
            )
        report_frames.append(report)

    volumes = pd.concat(report_frames, ignore_index=True, copy=False)
    return volumes


def _compute_volumes_for_period(partitions, reports, cell_name, env='prod'):
    """Load reports and calculate interval volumes."""
    num_reports = len(reports)
    _LOGGER.info('Loading %s reports', num_reports)
    timing_start = time.time()

    volume_frames = []
    capacity_frames = []
    report_period = 0
    for i, report in reports.iterrows():
        report_date = report['date'].isoformat()
        _progress(i, num_reports, report_date)

        try:  # We don't want a glitch to stop the entire endeavour
            servers, allocs, apps = get_interval_report(
                report_date, cell_name, env
            )
            volumes, capacity = volumes_for_interval(
                partitions, servers, allocs, apps
            )
            volumes['volume'] *= report['dt']  # measured in node-seconds
            capacity.loc[:, VOLUME_COLUMNS] *= report['dt']

            volume_frames.append(volumes)
            capacity_frames.append(capacity)

            report_period += report['dt']
        except BaseException:  # really catch everything pylint: disable=W0703
            _progress_complete()
            _LOGGER.error(
                'Failed to load %s report %s',
                cell_name, report_date
            )
            _LOGGER.error(traceback.format_exc())

    volumes = pd.concat(volume_frames, ignore_index=True, copy=False)
    capacities = pd.concat(capacity_frames, ignore_index=True, copy=False)

    _progress_complete()
    _LOGGER.info('Processed %s intervals in %d seconds.',
                 num_reports, time.time() - timing_start)

    volumes = volumes.groupby(
        ['partition', 'allocation']
    )['volume'].sum().reset_index()
    volumes['volume'] /= report_period  # measured in node-periods
    # Scale up volumes by 100 to match legacy results magnitude
    volumes['volume'] *= 100.0

    capacities = capacities.groupby(
        'partition'
    ).agg(VOLUME_AGGREGATORS).reset_index()
    capacities.loc[:, VOLUME_COLUMNS] /= report_period
    # Scale up volumes by 100 to match legacy results magnitude
    capacities['volume'] *= 100.0

    return volumes, capacities


def volumes_for_interval(partitions, servers, allocs, apps):
    """Prepare report of volumes per allocation for given interval."""
    partition_servers = servers.loc[
        servers['state'] == 'up', SERVER_COLUMNS
    ].groupby('partition')

    def tiered_volume(row):
        """Multiply the volume by the partition's tier."""
        return row['volume'] * partitions.get(row.name, NO_PARTITION)['tier']

    capacity = partition_servers.agg(SERVER_AGGREGATORS)
    capacity.rename(columns={'name': 'volume'}, inplace=True)
    capacity['volume'] = capacity.apply(tiered_volume, axis=1)

    partition_allocs = allocs[ALLOCS_COLUMNS].groupby('partition')

    partition_apps = apps.loc[
        apps['pending'] == 0, APPS_COLUMNS
    ].groupby('partition')

    volume_frames = []
    # Only iterate over partitions with servers, otherwise we don't have
    # total size to calculate capacity ratios and total volumes
    for partition, partition_size in capacity.iterrows():
        if partitions.get(partition, NO_PARTITION)['private']:
            volume = PRIVATE_PARTITION_DF.copy()
            volume.at[0, 'volume'] = partition_size['volume']
        else:
            volume = _compute_volumes_for_interval(
                partition_size,
                get_group(partition, partition_allocs),
                get_group(partition, partition_apps)
            )
            volume.reset_index(inplace=True)
            volume.rename(columns={'name': 'allocation'}, inplace=True)

        volume['partition'] = partition
        volume_frames.append(volume[['partition', 'allocation', 'volume']])

    volumes = pd.concat(volume_frames, ignore_index=True, copy=False)
    capacity.reset_index(inplace=True)
    return volumes, capacity


def _compute_volumes_for_interval(partition_size, allocs, apps):
    """Prepare volumes per allocation for given interval reports."""
    # Reserved and scheduled capacity for each allocation
    reserved = allocs.set_index('name')
    scheduled = apps.groupby('allocation').agg(CAPACITY_AGGREGATORS)

    # Capacity ratios for reserved and scheduled
    total_capacity = partition_size[DIMENSIONS]
    reserved[DIMENSIONS] /= total_capacity
    scheduled[DIMENSIONS] /= total_capacity

    # Find the dominants
    res_ratio = reserved[DIMENSIONS].apply(np.max, axis=1)
    res_ratio.name = 'res_ratio'
    sch_ratio = scheduled[DIMENSIONS].apply(np.max, axis=1)
    sch_ratio.name = 'sch_ratio'

    # Compute chargeback ratios
    chargeback = pd.concat([res_ratio, sch_ratio], axis=1, copy=False)
    chargeback.index.name = 'allocation'
    chargeback.fillna(0, inplace=True)

    def chargeback_ratio(row):
        """Compute chargeback ration based on scheduled vs reserved."""
        reserved = row['res_ratio']
        scheduled = row['sch_ratio']
        if scheduled >= reserved:
            return scheduled
        return scheduled + DISCOUNT * (reserved - scheduled)
    chargeback['ratio'] = chargeback.apply(chargeback_ratio, axis=1)

    # Compute volume by allocation
    chargeback['volume'] = (
        chargeback['ratio'] * partition_size['volume']
    )

    return chargeback[['volume']]


def list_interval_reports(start, end, cell_name, env='prod'):
    """Get available reports for a cell as a list of datetimes."""
    reports_dir = INTERVAL_DIR.format(cell=cell_name, env=env)
    files = sorted(
        f for f in os.listdir(reports_dir) if INTERVAL_FILENAME.match(f)
    )
    dates = sorted({
        datetime.strptime(f.partition('_')[0], '%Y-%m-%dT%H:%M:%S')
        for f in files
    })
    reports = pd.DataFrame({'date': dates})
    reports = reports.loc[
        (reports['date'] >= start) & (reports['date'] < end)
    ].reset_index(drop=True)

    # Calculate the duration of each interval in seconds
    reports['timestamp'] = reports['date'].apply(
        lambda report_date: int(time.mktime(report_date.utctimetuple()))
    )
    reports['dt'] = reports['timestamp'].shift(-1) - reports['timestamp']

    # We don't have an interval duration for the last file
    reports['dt'].fillna(reports['dt'].median(), inplace=True)

    return reports


def get_interval_report(report_date, cell_name, env='prod'):
    """Get all 3 reports for a given report date."""
    reports_dir = INTERVAL_DIR.format(cell=cell_name, env=env)
    return [
        pd.read_csv(os.path.join(
            reports_dir,
            '{}_{}.csv.bz2'.format(report_date, report_type)
        ))
        for report_type in ['servers', 'allocations', 'apps']
    ]


def list_daily_reports(start, end, cell_name, env='prod'):
    """Get available daily reports for a cell."""
    reports_dir = DAILY_DIR.format(cell=cell_name, env=env)
    files = sorted(
        f for f in os.listdir(reports_dir) if DAILY_FILENAME.match(f)
    )
    dates = [
        datetime.strptime(f.partition('.')[0], '%Y-%m-%d')
        for f in files
    ]
    reports = pd.DataFrame(
        list(zip(files, dates)),
        columns=['filename', 'date']
    )
    reports = reports.loc[
        (reports['date'] >= start) & (reports['date'] < end)
    ].reset_index(drop=True)

    reports['timestamp'] = reports['date'].apply(
        lambda report_date: int(time.mktime(report_date.utctimetuple()))
    )

    reports['dt'] = DAILY_REPORT_PERIOD

    return reports


def list_monthly_reports(month, env):
    """Get available monthly reports for all cells."""
    reports_dir = MONTHLY_DIR.format(env=env)
    report_name = '{}.csv'.format(month)
    cells = sorted(
        cell
        for cell in os.listdir(reports_dir)
        if os.path.isdir(os.path.join(reports_dir, cell))
    )
    reports = []
    for cell in cells:
        filename = os.path.join(reports_dir, cell, report_name)
        if os.path.isfile(filename):
            reports.append((cell, filename))
        else:
            _LOGGER.warning('Cell %s has no report for %s', cell, month)
    return reports


def _add_alloc_tenant(volumes):
    """Split tenant from alloc name in a volumes DataFrame."""
    volumes['tenant'] = ''

    def get_alloc_tenant(alloc):
        """Split the tenant from the allocation name."""
        if alloc == PRIVATE_PARTITION_LABEL:
            return pd.Series({
                'tenant': PRIVATE_PARTITION_LABEL,
                'allocation': PRIVATE_PARTITION_LABEL
            })

        if '/' not in alloc:
            _LOGGER.error('Allocation "%s" has no tenant', alloc)
            return pd.Series({'tenant': '', 'allocation': alloc})

        tenant, alloc = alloc.rsplit('/', 1)
        # Rewrite tenant name in the format found in LDAP
        ldap_tenant = ':'.join(tenant.split('/'))
        return pd.Series({'tenant': ldap_tenant, 'allocation': alloc})

    volumes.loc[:, ['tenant', 'allocation']] = volumes['allocation'].apply(
        get_alloc_tenant
    )


def _add_alloc_system_env(partitions, volumes):
    """Add allocation systems and env to a volumes DataFrame."""
    get_alloc_systems, get_alloc_env = _alloc_info_factory(
        partitions, volumes
    )

    # Add system ids
    volumes['system'] = volumes[['partition', 'tenant', 'allocation']].apply(
        get_alloc_systems, axis=1
    )

    # Distribute volume of multi-system allocs among all its system ids
    _distribute_system_volumes(volumes)

    volumes['system'] = volumes['system'].fillna(ID_UNKNOWN_TENANT).astype(int)

    # Add environments
    volumes['env'] = volumes[['tenant', 'allocation']].apply(
        get_alloc_env, axis=1
    )


def _distribute_system_volumes(volumes):
    """Distribute volume of multi-system allocs among all its system ids."""
    # DataFrame.apply may call function multiple times, need a set for rows
    new_rows = set()

    def pick_first_system(row):
        """Alter the row to contain only the first system id.

        The remaining system ids are saved for later in `new_rows`, and the
        volumes are distributed among all system ids.
        """
        systems = row['system'].split(':')
        new_volume = row['volume'] / len(systems)
        for new_system in systems[1:]:
            new_rows.add(tuple({  # Mutate closure variable
                'partition': row['partition'],
                'tenant': row['tenant'],
                'allocation': row['allocation'],
                'volume': new_volume,
                'system': new_system
            }.items()))
        return pd.Series({
            'system': systems[0],
            'volume': new_volume
        })

    # Modify the systems and volumes of existing rows in place
    volumes.loc[
        volumes['system'].str.contains(':'), ['system', 'volume']
    ] = volumes.loc[
        volumes['system'].str.contains(':'), :
    ].apply(pick_first_system, axis=1)

    # Add the new rows extracted from multi-system rows
    for row in new_rows:
        volumes.loc[volumes.index.max() + 1] = pd.Series(dict(row))


def _alloc_info_factory(partitions, volumes):
    """Prepare functions that provide information on allocations.

    These functions are intended to be applied to an entire DataFrame.
    They require a good amount of data coming from the Firmwide Directory LDAP,
    from the proid db, and from Treadmill LDAP, so it's cleaner to prepare the
    data in a closure here, then return only the functions.
    """
    # Fetch mailgroup info from Firmwide Directory LDAP
    mailgroup_queries = sorted(set(
        volumes.loc[
            volumes['allocation'].str.contains('@'), 'allocation'
        ].str.split('@').apply(lambda i: i[-1])
    ))
    mailgroups = {}
    fwd = admin.Admin(FWD_HOST, FWD_BASE)
    fwd.connect()
    for group in mailgroup_queries:
        results = fwd.search(
            FWD_BASE,
            '(&(cn={cn}))'.format(cn=group),
            attributes=['mseonid', 'msenvironment']
        )
        for _, result in results:
            mailgroups[group] = {
                'system': [
                    int(i) for i in result.get('mseonid', [ID_UNKNOWN_TENANT])
                ],
                'env': ':'.join(
                    env.lower() for env in result.get('msenvironment', [])
                )
            }

    # Fetch proid info from ProidDB
    proid_queries = sorted(set(
        volumes.loc[
            (volumes['tenant'] == admin.DEFAULT_TENANT) &
            (~volumes['allocation'].str.contains('@')),
            'allocation'
        ]
    ))
    cursor = proiddb.connect()
    proids = {
        proid: {
            'system': (
                proiddb.eonid(proid, cursor=cursor) or ID_UNKNOWN_TENANT
            ),
            'env': proiddb.environment(proid, cursor=cursor)
        }
        for proid in proid_queries
    }

    # Fetch tenant system ids from Treadmill's LDAP
    tenant_systems = {
        tenant['tenant']: tenant['systems']
        for tenant in admin.Tenant(context.GLOBAL.ldap.conn).list({})
    }

    # Fetch allocation environment from Treadmill's LDAP
    alloc_env = {
        alloc['_id']: alloc['environment']
        for alloc in admin.Allocation(context.GLOBAL.ldap.conn).list({})
    }

    def get_alloc_systems(row):
        """Get the system ids of an allocation."""
        alloc = row['allocation']
        if alloc == PRIVATE_PARTITION_LABEL:
            # Private partition, look at partition systems
            systems = partitions.get(row['partition'], NO_PARTITION)['systems']
            if not systems:
                systems = TREADMILL_SYSTEMS
        elif '@' in alloc:
            # Personal container, look at mailgroup systems
            systems = mailgroups.get(
                alloc.split('@', 1)[-1], {}
            ).get('system', [ID_UNKNOWN_TENANT])
        elif row['tenant'] == admin.DEFAULT_TENANT:
            # Opportunistic app, look at proid systems
            systems = [
                proids.get(alloc, {}).get('system', ID_UNKNOWN_TENANT)
            ]
        else:
            # Plain old regular allocation, look at tenant systems
            systems = tenant_systems.get(row['tenant'], [ID_UNKNOWN_TENANT])
        return ':'.join(str(system) for system in systems)

    def get_alloc_env(row):
        """Get the environment of an allocation."""
        alloc = row['allocation']
        if '@' in alloc:
            # Personal container
            return mailgroups.get(alloc.split('@', 1)[-1], {}).get('env', '')
        elif row['tenant'] == admin.DEFAULT_TENANT:
            # Opportunistic app
            return proids.get(alloc, {}).get('env', '')
        return alloc_env.get('{}/{}'.format(row['tenant'], alloc), '')

    return get_alloc_systems, get_alloc_env


def _add_partition_stats(
        volumes, total_alloc_volume, total_part_volume, part_capacities):
    """Add various partition statistics to a volumes DataFrame."""
    part_stats = []
    for partition in part_capacities.groups:
        capacity = part_capacities.get_group(partition)
        part_stats.extend([
            (
                partition, ID_CELL_MEM, TOTAL_CELL_MEM,
                capacity['mem'].iat[0]
            ),
            (
                partition, ID_CELL_CPU, TOTAL_CELL_CPU,
                capacity['cpu'].iat[0]
            ),
            (
                partition, ID_CELL_DISK, TOTAL_CELL_DISK,
                capacity['disk'].iat[0]
            ),
            (
                partition, ID_CELL_VOL, TOTAL_CELL_VOLUME,
                total_part_volume[partition]
            )
        ])
        if partition in total_alloc_volume:
            part_stats.append((
                partition, ID_ALLOC_VOL, TOTAL_ALLOC_VOLUME,
                total_alloc_volume[partition]
            ))
    for stat in part_stats:
        volumes.loc[volumes.index.max() + 1] = pd.Series({
            'partition': stat[0],
            'system': stat[1],
            'tenant': CELL_STATS_LABEL,
            'allocation': stat[2],
            'env': '',
            'volume': stat[3]
        })


def _adjust_volumes(volumes, total_alloc_volume, total_part_volume):
    """Adjust volumes to fit partition by discounting or shredding.

    Adjustment is done only for non-private partitions.
    """
    # total_alloc_volume contains only non-private partitions, but
    # total_part_volume has private partitions too, so dropna to ignore them
    delta_volume = (total_alloc_volume - total_part_volume).dropna()
    ratio_volume = (total_part_volume / total_alloc_volume).dropna()
    for partition, delta in delta_volume.iteritems():
        if delta > 0:
            # Ensure users are not billed for more than the volume of the cell
            volumes.loc[
                (volumes['partition'] == partition) & (volumes['system'] > 0),
                'volume'
            ] *= ratio_volume[partition]
        elif delta < 0:
            # Assign all unused volume in this partition to the system id
            # configured for this, so that all volume is accounted for.
            volumes.loc[volumes.index.max() + 1] = pd.Series({
                'partition': partition,
                'system': UNUSED_VOLUME_SYSTEMID,
                'tenant': UNUSED_VOLUME_TENANT,
                'allocation': UNUSED_VOLUME_LABEL,
                'env': 'prod',
                'volume': -1 * delta
            })


def get_cell_partitions(cell_name):
    """Get information about all partitions in a cell."""
    partitions = {}
    ldap_partitions = admin.Partition(context.GLOBAL.ldap.conn).list({})
    for partition in ldap_partitions:
        if partition['cell'] != cell_name:
            continue

        name = partition['partition']
        systems = [
            system
            for system in partition['systems']
            if system not in TREADMILL_SYSTEMS
        ]

        # Private if it's associated to any other system but Treadmill's
        is_private = (len(systems) > 0)

        # Assume the partition is called by the tier, otherwise it's all solid
        # TODO in the future the tier should be in the LDAP partition entry
        tier = TIERS.get(name, TIERS['solid'])

        partitions[name] = {
            'systems': systems,
            'private': is_private,
            'tier': tier
        }
    return partitions


def get_group(name, groups):
    """Safely get a group from a DataFrameGroupBy.

    If the group doesn't exist, return an empty DataFrame with the same
    columns as any other group that does.
    """
    try:
        return groups.get_group(name)
    except KeyError:
        some_group = groups.groups.keys()[0]
        return pd.DataFrame(columns=groups.get_group(some_group).columns)


def _progress(current, total, label):
    """Print a progress report."""
    if not INTERACTIVE:
        return
    print(
        'Report {:6}/{:6}: {}'.format(current + 1, total, label),
        end='\r'
    )


def _progress_complete():
    """Print a blank line to preserve the progress report."""
    if not INTERACTIVE:
        return
    print()
