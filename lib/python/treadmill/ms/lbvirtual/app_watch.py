"""Watch for changes in collection of app endpoints and update virtuals (pool).

AppWatch monitors changes in app endpoints for all apps that match a lbendpoint
pattern and compares endpoints with the current virtual members. Extra services
will be removed, missing will be added.

There will be one AppWatch per location, each watching all cells in that region
and managing its virtuals, LBControl doesn't handle concurrent virtual updates.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import glob
import hashlib
import io
import logging
import os
import time

from treadmill import admin
from treadmill import context
from treadmill import exc
from treadmill import utils
from treadmill import yamlwrapper as yaml

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import lbendpoint as tm_lbendpoint
from treadmill.ms import lbvirtual

_LOGGER = logging.getLogger(__name__)

_EXCEPTION_RETRY_INTERVAL = 60


def _get_lbvirtual_vips(cells):
    """Get the lbvirtual vips for the given cells."""
    vips = set()
    admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
    for cell_name in cells:
        cell = admin_cell.get(cell_name)
        vips.update(vip for vip in cell['data']['lbvirtual']['vips']
                    if vip.startswith('treadmill-'))
    return vips


class VirtualAppWatch(object):
    """LBVirtual app watcher"""

    _APP_GROUPS_DIR = 'app-groups'
    _ENDPOINTS_DIR = 'endpoints'

    def __init__(self, lbc, fs_root, partition, total_partitions,
                 watch_cells, watch_groups):
        self.lbc = lbc
        self.fs_root = fs_root
        self.partition = partition
        self.total_partitions = total_partitions
        self.watch_cells = watch_cells
        self.watch_groups = watch_groups

        self.vips = _get_lbvirtual_vips(watch_cells)
        _LOGGER.info('Vips: %r', self.vips)

        self.state = {}

    def _filter_virtuals(self, virtuals):
        """Filter virtuals based on the vips for the watched cells."""

        return [virtual for virtual in virtuals
                if virtual.rsplit('.', 1)[0] in self.vips]

    def sync(self):
        """Sync the lbendpoints for this partition and watched cells."""
        lbendpoints = self.get_lbendpoints()
        _LOGGER.debug('lbendpoints: %r', lbendpoints)

        # Delete removed lbendpoints.
        removed_lbendpoints = set(self.state.keys()) - set(lbendpoints)
        for removed_lbendpoint in removed_lbendpoints:
            del self.state[removed_lbendpoint]

        # Configure the rest, wait _EXCEPTION_RETRY_INTERVAL after exception.
        for lbendpoint in lbendpoints:
            lb_state = self.state.setdefault(lbendpoint, {})

            try:
                exception_time = lb_state['exception']['time']
            except KeyError:
                exception_time = 0
            if time.time() < exception_time + _EXCEPTION_RETRY_INTERVAL:
                _LOGGER.info(
                    '%s is in exception state: %r, retry interval: %d',
                    lbendpoint, lb_state['exception'],
                    _EXCEPTION_RETRY_INTERVAL
                )
                continue

            try:
                if self.configure_lbendpoint(lbendpoint, lb_state):
                    lb_state.pop('exception', None)
                else:
                    del self.state[lbendpoint]
            except Exception as err:  # pylint: disable=W0703
                _LOGGER.exception('Error configuring %s', lbendpoint)
                lb_state['exception'] = {'err': err, 'time': time.time()}

    def get_lbendpoints(self):
        """Get the lbendpoints to sync for this partition and watched cells."""
        # Get the lbendpoints from all watched zk2fs mirrors.
        # Partitioning is based on app group (lbendpoint) name (not file path).
        app_groups_pattern = os.path.join(
            self.fs_root, '*', self._APP_GROUPS_DIR, '*'
        )

        lbendpoints = set()
        for app_group_file in glob.glob(app_groups_pattern):
            app_group_name = os.path.basename(app_group_file)

            if app_group_name.startswith('.'):
                continue

            if (int(hashlib.md5(app_group_name.encode()).hexdigest(), 16) %
                    self.total_partitions != self.partition):
                continue

            if not self._filter_app_group(app_group_file):
                continue

            lbendpoints.add(app_group_name)
        return lbendpoints

    def _filter_app_group(self, app_group_file):
        """Filter app group based on the group type and cells."""
        try:
            with io.open(app_group_file) as f:
                app_group = yaml.load(stream=f)
        except IOError as err:
            if err.errno != errno.ENOENT:
                raise
            _LOGGER.debug('File not found: %s', app_group_file)
            return False

        if app_group['group-type'] not in self.watch_groups:
            return False

        if not set(self.watch_cells) & set(app_group.get('cells', [])):
            return False

        return True

    def configure_lbendpoint(self, lbendpoint, lb_state):
        """Configure lbendpoint, get target members and configure virtuals."""
        _LOGGER.info('Configuring lbendpoint %s', lbendpoint)

        # Get the most recent lbendpoint config file and its mtime.
        lbendpoint_file, lbendpoint_mtime = self.get_config(lbendpoint)
        if not lbendpoint_file:
            _LOGGER.info('Removing lbendpoint state, file deleted.')
            return False

        # Load lbendpoint config from file if mtime changed (or no config yet).
        if lbendpoint_mtime != lb_state.get('lbendpoint_mtime'):
            _LOGGER.info(
                'Loading lbendpoint config, file: %s, mtime: %s',
                lbendpoint_file, lbendpoint_mtime
            )
            try:
                cells, pattern, endpoint, virtuals = self.load_config(
                    lbendpoint_file
                )
            except IOError as err:
                if err.errno != errno.ENOENT:
                    raise
                _LOGGER.info('Removing lbendpoint state, file deleted.')
                return False

            _LOGGER.info(
                'cells: %s, pattern: %s, endpoint: %s, virtuals: %r',
                cells, pattern, endpoint, virtuals
            )
            lb_state.update({
                'lbendpoint_mtime': lbendpoint_mtime,
                'cells': cells,
                'pattern': pattern,
                'endpoint': endpoint,
                'virtuals': {virtual: {'check': False} for virtual in virtuals}
            })

        # Get the target lbendpoint members and configure virtuals.
        target_members = self.get_endpoints(
            lb_state['cells'], lb_state['pattern'], lb_state['endpoint']
        )
        _LOGGER.info('Target lbendpoint members: %r', target_members)

        for virtual in lb_state['virtuals']:
            self.configure_virtual(
                virtual, lb_state['virtuals'][virtual], target_members
            )

        return True

    def get_config(self, lbendpoint):
        """Get the most recent lbendpoint config file and its mtime."""
        res_file, res_mtime = None, None
        # Check all watched cells.
        for cell_name in self.watch_cells:
            lbendpoint_file = os.path.join(
                self.fs_root, cell_name, self._APP_GROUPS_DIR, lbendpoint
            )
            try:
                lbendpoint_mtime = os.stat(lbendpoint_file).st_mtime
                if res_mtime is None or res_mtime < lbendpoint_mtime:
                    res_file, res_mtime = lbendpoint_file, lbendpoint_mtime
            except OSError as err:
                if err.errno != errno.ENOENT:
                    raise
        return res_file, res_mtime

    def load_config(self, lbendpoint_file):
        """Load lbendpoint config from file and validate."""
        with io.open(lbendpoint_file) as f:
            app_group = yaml.load(stream=f)
            _LOGGER.debug('app_group: %r', app_group)

        lbendpoint = tm_lbendpoint.group2lbendpoint(app_group)
        _LOGGER.debug('lbendpoint: %r', lbendpoint)

        schema = [
            ('cells', True, list),
            ('pattern', True, str),
            ('endpoint', True, str),
        ]
        if 'virtual' in lbendpoint:
            schema.append(('virtual', True, str))
        else:
            schema.append(('virtuals', True, list))

        try:
            utils.validate(lbendpoint, schema)
        except exc.InvalidInputError:
            _LOGGER.exception('Invalid lbendpoint config: %r', lbendpoint)
            raise

        cells = lbendpoint['cells']
        pattern = lbendpoint['pattern']
        endpoint = lbendpoint['endpoint']
        if 'virtual' in lbendpoint:
            virtuals = self._filter_virtuals([lbendpoint['virtual']])
        else:
            virtuals = self._filter_virtuals(lbendpoint['virtuals'])

        return cells, pattern, endpoint, virtuals

    def get_endpoints(self, cells, pattern, endpoint):
        """Get the target lbendpoint members."""
        if '.' not in pattern:
            _LOGGER.warning('Invalid lbendpoint pattern: %s', pattern)
            return set()

        proid, app_pattern = pattern.split('.', 1)
        if '#' not in app_pattern:
            app_pattern = app_pattern + '#*'
        # Get the endpoints from the watched zk2fs mirrors for the given cells.
        # LB virtuals work only for tcp endpoints.
        hostports = set()
        for cell_name in cells:
            file_pattern = os.path.join(
                self.fs_root, cell_name, self._ENDPOINTS_DIR,
                proid, app_pattern + ':tcp:' + endpoint
            )
            matches = glob.glob(file_pattern)
            for match in matches:
                try:
                    with io.open(match) as f:
                        hostports.add(f.read())
                except IOError as err:
                    if err.errno != errno.ENOENT:
                        raise
                    _LOGGER.debug('File not found: %s', match)

        return hostports

    def configure_virtual(self, virtual, virt_state, target_members):
        """Configure virtual given the current state and target members."""
        _LOGGER.info('Configuring virtual %s', virtual)

        members = virt_state.get('members')
        if virt_state['check']:
            lbvirtual.check_pool_health(self.lbc, virtual, fix=True)
            virt_state['check'] = False
        if members != target_members:
            try:
                lbvirtual.update_pool_members(
                    self.lbc, virtual, target_members
                )
            except Exception:
                # Updating pool members failed, check the pool health on retry.
                virt_state['check'] = True
                raise
            virt_state['members'] = target_members
        else:
            _LOGGER.info('Virtual %s is up-to-date.', virtual)
