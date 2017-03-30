"""Admin Cell CLI module"""
from __future__ import absolute_import

import logging
import treadmill
import os
import click
import errno
from ansible.cli.playbook import PlaybookCLI
from distutils.dir_util import copy_tree

_LOGGER = logging.getLogger(__name__)


def init():
    """Admin Cell CLI module"""

    @click.group()
    def aws():
        """Manage treadmill on AWS"""
        pass

    def _get_from_treadmill_egg(obj):
        return os.path.join(treadmill.TREADMILL_DEPLOY_PACKAGE,  obj)

    @aws.command(name='init')
    def init():
        """Initialise ansible files for AWS deployment"""
        destination_dir = os.getcwd() + '/deploy'
        try:
            os.makedirs(destination_dir)
        except OSError as e:
            if e.errno == errno.EEXIST:
                print('''AWS "deploy" directory already exists in this folder
                \n''', destination_dir)
        copy_tree(_get_from_treadmill_egg('../deploy'), destination_dir)

    @aws.command(name='cell')
    @click.option('--create', required=False, is_flag=True,
                  help='Create a new treadmill cell on AWS',)
    @click.option('--destroy', required=False, is_flag=True,
                  help='Destroy treadmill cell on AWS',)
    @click.option('--playbook', help='Playbok file',)
    @click.option('--inventory',
                  default=_get_from_treadmill_egg('controller.inventory'),
                  help='Inventory file',)
    @click.option('--key-file',
                  default='key.pem',
                  help='AWS ssh pem file',)
    @click.option('--aws-config',
                  default=_get_from_treadmill_egg('aws.yml'),
                  help='AWS config file',)
    def cell(create, destroy, playbook, inventory, key_file, aws_config):
        """Manage treadmill cell on AWS"""

        playbook_args = [
            'ansible-playbook',
            '-i',
            inventory,
            '-e',
            'aws_config={}'.format(aws_config),
        ]

        if create:
            playbook_args.extend([
                playbook or _get_from_treadmill_egg('cell.yml'),
                '--key-file',
                key_file,
            ])
        elif destroy:
            playbook_args.append(
                playbook or _get_from_treadmill_egg('destroy-cell.yml')
            )
        else:
            return

        playbook_cli = PlaybookCLI(playbook_args)
        playbook_cli.parse()
        playbook_cli.run()

    @aws.command(name='node')
    @click.option('--create',
                  required=False,
                  is_flag=True,
                  help='Create a new treadmill node',)
    @click.option('--playbook',
                  default=_get_from_treadmill_egg('node.yml'),
                  help='Playbok file',)
    @click.option('--inventory',
                  default=_get_from_treadmill_egg('controller.inventory'),
                  help='Inventory file',)
    @click.option('--key-file',
                  default='key.pem',
                  help='AWS ssh pem file',)
    @click.option('--aws-config',
                  default=_get_from_treadmill_egg('aws.yml'),
                  help='AWS config file',)
    def node(create, playbook, inventory, key_file, aws_config):
        """Manage treadmill node"""
        if create:
            playbook_cli = PlaybookCLI([
                'ansible-playbook',
                '-i',
                inventory,
                playbook,
                '--key-file',
                key_file,
                '-e',
                'aws_config={}'.format(aws_config),
            ])
            playbook_cli.parse()
            playbook_cli.run()

    del cell
    del node

    return aws
