"""Syncronize DNS data with Zookeeper file system mirror.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import glob
import io
import logging
import os

import six

from treadmill import utils
from treadmill import yamlwrapper as yaml

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import dyndnsclient


_LOGGER = logging.getLogger(__name__)

DEFAULT_WEIGHT = 10
DEFAULT_PRIORITY = 10


class DnsSync(object):
    """Syncronizes DynDNS with Zk mirror on disk."""

    def __init__(self, cell, dyndns_servers, zone, fs_root, scopes, masters):
        self.cell = cell
        self.dyndns_client = dyndnsclient.DyndnsClient(dyndns_servers)
        self.fs_root = fs_root

        self.state = None
        self.servers = set()
        self.masters = masters
        if self.masters is None:
            self.masters = set()

        self.scopes = {
            'cell': cell,
        }
        self.scopes.update(scopes)

        self.zone = zone
        self.zones = ['.'.join([scope, scope_name, self.zone])
                      for scope_name, scope in six.iteritems(self.scopes)]

    def _srv_rsrc(self, name, scope, proto, endpoint, hostport):
        """Return tuple of resource endpoint/payload."""
        host, port = hostport.split(':')
        if scope not in self.scopes:
            _LOGGER.warning('Unsupported scope: %s', scope)
            return None

        if proto not in ['tcp', 'udp']:
            _LOGGER.warning('Unsupported proto: %s', proto)
            return None

        zone = '.'.join([self.scopes[scope], scope, self.zone])
        url = 'srv/%s/_%s._%s.%s' % (zone, endpoint, proto, name)
        return str(url), 'target', str(host), 'port', int(port)

    def _cname_rsrc(self, zone, name, host):
        """Returns tuple of resource endpoint/payload."""
        url = 'cname/%s/%s.%s' % (zone, name, self.cell)
        return str(url), 'target', str(host)

    def _fully_qualified(self, zone, target):
        """Check if target is fqdn, and if not, appends zone to the name."""
        if target[-1] == '.':
            return str(target.rstrip('.'))
        else:
            return str(target + '.' + zone)

    def _current_records(self, zone):
        """Return all records found in DNS for the given cell."""
        _LOGGER.info('Query state for: %s', zone)
        axfr_endpoint = 'zone/axfr/%s' % zone
        all_records = self.dyndns_client.get(axfr_endpoint)

        _LOGGER.debug('Records for zone: %s', zone)
        for record in all_records:
            _LOGGER.debug('%r', record)

        cell_records = [record for record in all_records
                        if self._is_cell_record(record)]

        _LOGGER.debug('Filtered ecords for zone: %s', zone)
        for record in cell_records:
            _LOGGER.debug('%r', record)

        _LOGGER.info('Total records: %s, cell records: %s',
                     len(all_records), len(cell_records))

        result = set()
        for rec in cell_records:
            rtype = rec['type'].lower()
            name = rec['name']

            # TODO: Need to confirm that this is correct logic.
            #                Ideally dyndns API should return fully qualified
            #                names.
            #                To be confirmed / fixed during code review.
            target = self._fully_qualified(zone, rec['target'])

            if rtype == 'srv':
                url = str('srv/%s/%s' % (zone, name))
                port = int(rec['port'])
                result.add((url, 'target', target, 'port', port))
            elif rtype == 'cname':
                url = str('cname/%s/%s' % (zone, name))
                result.add((url, 'target', target))
            else:
                _LOGGER.info('Unsupport record: %r', rec)

        return result

    # def _cnames(self, alias, pattern):
    #     """Return list of cnames to be created given alias and pattern."""
    #     result = set()
    #     proid, app_pattern = appgroup['pattern'].split('.', 1)
    #     # Create CNAME using ssh endpoint.
    #     ssh_pattern = os.path.join(self.fs_root, 'endpoints', proid,
    #                                app_pattern + '#[0-9]*:ssh')
    #     matching = glob.glob(ssh_pattern)
    #     for match in matching:
    #         instance_name = '-'.join([
    #             alias,
    #             match[match.find('#') + 1:-len(':ssh')]
    #         ])
    #         instance_fqdn = '.'.join([
    #             instance_name,
    #             'apps',
    #             self.cell,
    #             self.zone
    #         ])
    #         try:
    #             with io.open(match) as f:
    #                 hostport = f.read()
    #                 host = hostport.split(':')[0]
    #                 result.add(self._cname_rsrc(instance_name, host))
    #                 result.add(self._cname_rsrc(alias, instance_fqdn))
    #         except IOError:
    #             _LOGGER.info('Endpoint removed: %s', match)
    #     return result

    def _srv_records(self, alias, scope, pattern, endpoint):
        """Return srv records matched by pattern."""
        result = set()

        proid, app_pattern = pattern.split('.', 1)
        glob_pattern = os.path.join(self.fs_root, 'endpoints', proid,
                                    app_pattern + '#[0-9]*:*:' + endpoint)
        matching = glob.glob(glob_pattern)
        _LOGGER.debug('matching: %r', matching)

        for match in matching:
            _app, proto, _endpoint = match.split(':')
            try:
                with io.open(match) as f:
                    hostport = f.read()
                    srv_rec_rsrc = self._srv_rsrc(alias, scope, proto,
                                                  endpoint, hostport)
                    if srv_rec_rsrc:
                        result.add(srv_rec_rsrc)
            except IOError:
                _LOGGER.info('Endpoint removed: %s', match)

        return result

    def _match_appgroup(self, appgroup):
        """For all endpoints that match the appgroup, add to target state."""
        _LOGGER.debug('appgroup: %r', appgroup)
        if appgroup['group-type'] != 'dns':
            return set()

        data = utils.equals_list2dict(appgroup.get('data'))
        _LOGGER.debug('data: %r', data)
        # Top level API must ensure that alias is always set, even it user
        # selects app pattern as alias (default).
        alias = data.get('alias')
        if not alias:
            _LOGGER.error('No alias supplied for %r', appgroup)
            return set()

        scope = data.get('scope', 'cell')

        result = set()
        for endpoint in appgroup['endpoints']:
            srvs = self._srv_records(
                alias, scope, appgroup['pattern'], endpoint
            )
            _LOGGER.debug('srvs: %r', srvs)
            result.update(srvs)

        return result

    def _target_records(self):
        """Returns target state as defined by zk mirror on file system."""
        target_records = set()
        appgroups_pattern = os.path.join(self.fs_root, 'app-groups', '*')
        for appgroup_f in glob.glob(appgroups_pattern):
            _LOGGER.debug('appgroup_f: %r', appgroup_f)
            if appgroup_f.startswith('.'):
                continue
            try:
                with io.open(appgroup_f) as f:
                    appgroup = yaml.load(stream=f)
                    target_records.update(self._match_appgroup(appgroup))
            except IOError:
                _LOGGER.info('Appgroup deleted: %s', appgroup_f)

        _LOGGER.debug('target_records: %r', target_records)
        return target_records

    def _update_cell_servers(self):
        """Update list of servers that belong to the cell."""
        servers_glob = glob.glob(os.path.join(self.fs_root, 'servers', '*'))
        self.servers = set(map(os.path.basename, servers_glob))

        _LOGGER.debug('Cell servers:')
        for server in sorted(self.servers):
            _LOGGER.debug('%s', server)

        for master in sorted(self.masters):
            _LOGGER.debug('master: %s', master)

    def _is_cell_record(self, record):
        """Check if record is managed by sync process of this cell."""
        target = record['target']
        # If target is fully qualified and is server of the cell.
        if target[-1] == '.' and target[:-1] in self.servers:
            return True

        if target[-1] == '.' and target[:-1] in self.masters:
            return True

        return False

    def sync(self):
        """Syncronizes current and target state."""
        self._update_cell_servers()

        if self.state is None:
            self.state = set()
            for zone in self.zones:
                self.state.update(self._current_records(zone))

        _LOGGER.debug('Current state:')
        for record in sorted(self.state):
            _LOGGER.debug('%r', record)

        target = self._target_records()

        _LOGGER.debug('Target state:')
        for record in sorted(target):
            _LOGGER.debug('%r', record)

        extra = self.state - target
        missing = target - self.state

        if not (extra or missing):
            _LOGGER.info('DNS is up to date.')

        def _req(item):
            """Constructs url and payload from tuple."""
            url = item[0]
            params = list(item[1:])
            payload = {k: v for k, v in zip(params[0::2], params[1::2])}
            return url, payload

        for item in extra:
            url, payload = _req(item)
            payload.update({
                'weight': DEFAULT_WEIGHT,
                'priority': DEFAULT_PRIORITY,
            })
            _LOGGER.info('del: %s, %r', url, payload)
            self.dyndns_client.delete(url, **payload)

        for item in missing:
            url, payload = _req(item)
            _LOGGER.info('add: %s, %r', url, payload)
            self.dyndns_client.post(url, **payload)

        self.state = target
