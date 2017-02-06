"""Bootstrap implementation for windows."""


import glob
import os

import treadmill

import treadmill.syscall.winsymlink  # pylint: disable=W0611

from .. import _bootstrap_base


_MASTER_NOT_SUPPORTED_MESSAGE = "Windows does not support master services."


def default_install_dir():
    """Gets the base install directory."""
    return "c:\\"


class WindowsBootstrap(_bootstrap_base.BootstrapBase):
    """Base interface for bootstrapping on windows."""

    def _rename_file(self, src, dst):
        """Rename the specified file"""
        # file cannot be renamed if the target exists
        # so delete the file
        if os.path.exists(dst):
            os.remove(dst)

        super(WindowsBootstrap, self)._rename_file(src, dst)


class NodeBootstrap(WindowsBootstrap):
    """For bootstrapping the node on windows."""

    def __init__(self, dst_dir, defaults):
        super(NodeBootstrap, self).__init__(
            os.path.join(treadmill.TREADMILL, 'local', 'windows', 'node'),
            dst_dir,
            defaults
        )

    def _set_env(self):
        """Sets TREADMILL_ environment variables"""
        env_files = glob.glob(os.path.join(self.dst_dir, 'env', '*'))
        for env_file in env_files:
            with open(env_file, 'r') as f:
                env = f.readline()
                if env:
                    env = env.strip()
            os.environ[str(os.path.basename(env_file))] = env

    def run(self):
        """Runs the services."""
        params = self._params
        cmd = self._interpolate('{{ s6 }}\\winss-svscan.exe', params)
        arg = self._interpolate('{{ dir }}\\init', params)
        self._set_env()
        # needed for winss-svscan
        os.chdir(arg)

        os.execvp(cmd, [arg])

    def install(self):
        """Installs the services."""
        if os.path.exists(os.path.join(self.src_dir, 'wipe_me')):
            os.system(os.path.join(self.src_dir, 'bin', 'wipe_node.cmd'))

        super(NodeBootstrap, self).install()


class MasterBootstrap(_bootstrap_base.BootstrapBase):
    """For bootstrapping the master on windows."""

    # pylint: disable=W0613, W0231
    def __init__(self, dst_dir, defaults, master_id):
        raise Exception(_MASTER_NOT_SUPPORTED_MESSAGE)

    def install(self):
        """Installs the services."""
        raise Exception(_MASTER_NOT_SUPPORTED_MESSAGE)

    def run(self):
        """Runs the services."""
        raise Exception(_MASTER_NOT_SUPPORTED_MESSAGE)
