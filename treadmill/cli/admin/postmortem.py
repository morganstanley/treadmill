"""
Collect node information post crash.
"""


import logging
import os
import shlex
import socket

import click

from treadmill import postmortem
from treadmill import utils
from treadmill.osmodules import bootstrap


_LOGGER = logging.getLogger(__name__)


def init():
    """Return top level command handler"""

    @click.group()
    @click.option('--install-dir',
                  default=lambda: os.path.join(bootstrap.default_install_dir(),
                                               'treadmill'),
                  help='Treadmill node install directory.')
    @click.option('--upload_script',
                  help='upload script to upload post-mortem file')
    @click.option('--upload_args',
                  help='arguments for upload script')
    @click.pass_context
    def collect(install_dir, upload_script, upload_args):
        """Collect Treadmill node data"""

        filetime = utils.datetime_utcnow().strftime('%Y%m%d_%H%M%SUTC')
        hostname = socket.gethostname()

        postmortem_file_base = os.path.join(
            '/tmp', '{0}-{1}.tar'.format(hostname, filetime)
        )

        postmortem_file = postmortem.collect(install_dir, postmortem_file_base)
        _LOGGER.info('generated postmortem file: %r', postmortem_file)
        # need to change owner of the postmortem file to treadmill proid
        # change permission to 644
        os.chmod(postmortem_file, 0o644)

        # if upload script is provided, we upload the postmortem_file
        if upload_script is not None:
            upload_arg_list = ([] if upload_args is None
                               else shlex.split(upload_args))
            utils.check_call(
                [upload_script, postmortem_file] + upload_arg_list
            )

    return collect
