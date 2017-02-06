"""Bootstrap implementation for linux."""


import abc
import logging
import os

import treadmill

from .. import _bootstrap_base

from ... import context


_LOGGER = logging.getLogger(__name__)


def default_install_dir():
    """Gets the base install directory."""
    return '/var/tmp'


class LinuxBootstrap(_bootstrap_base.BootstrapBase):
    """Base interface for bootstrapping on linux."""

    @property
    @abc.abstractproperty
    def _bin_path(self):
        """Gets the bin path."""

    def run(self):
        """Runs the services."""
        args = [os.path.join(self.dst_dir, self._bin_path)]
        os.execvp(args[0], args)


class NodeBootstrap(LinuxBootstrap):
    """For bootstrapping the node on linux."""

    def __init__(self, dst_dir, defaults):
        super(NodeBootstrap, self).__init__(
            os.path.join(treadmill.TREADMILL, 'local', 'linux', 'node'),
            dst_dir,
            defaults
        )

    @property
    def _bin_path(self):
        return os.path.join('bin', 'run.sh')

    def install(self):
        wipe_me = os.path.join(self.dst_dir, 'wipe_me')
        wipe_me_sh = os.path.join(self.dst_dir, 'bin', 'wipe_node.sh')

        _LOGGER.debug('wipe_me: %s, wipe_me.sh: %s', wipe_me, wipe_me_sh)
        if os.path.exists(wipe_me):
            _LOGGER.info('Requested clean start, calling: %s', wipe_me_sh)
            os.system(wipe_me_sh)
        else:
            _LOGGER.info('Preserving treadmill data, no clean restart.')

        super(NodeBootstrap, self).install()


class MasterBootstrap(LinuxBootstrap):
    """For bootstrapping the master on linux."""

    def __init__(self, dst_dir, defaults, master_id):
        super(MasterBootstrap, self).__init__(
            os.path.join(treadmill.TREADMILL, 'local', 'linux', 'master'),
            os.path.join(dst_dir, context.GLOBAL.cell, str(master_id)),
            defaults
        )
        self.master_id = int(master_id)
        self.defaults.update({'master-id': self.master_id})

    @property
    def _bin_path(self):
        return os.path.join('treadmill', 'bin', 'run.sh')

    @property
    def _params(self):
        """Overrides master params with current master."""
        params = super(MasterBootstrap, self)._params  # pylint: disable=W0212
        for master in params['masters']:  # pylint: disable=E1136
            if master['idx'] == self.master_id:
                params.update({'me': master})
        return params
