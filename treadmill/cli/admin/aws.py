"""Admin Cell CLI module"""
from __future__ import absolute_import

import logging

import click
from ansible.cli.playbook import PlaybookCLI

_LOGGER = logging.getLogger(__name__)


def init():
    """Admin Cell CLI module"""

    @click.group()
    def aws():
        """Manage treadmill on AWS"""
        pass

    @aws.command(name='cell')
    @click.option('--create', required=False, is_flag=True,
                  help='Create a new treadmill cell on AWS',)
    @click.option('--playbook', default='cell.yml',
                  help='Playbok file',)
    @click.option('--inventory', default='controller.inventory',
                  help='Inventory file',)
    @click.option('--key-file', default='key.pem',
                  help='AWS ssh pem file',)
    def cell(create, playbook, inventory, key_file):
        """Manage treadmill cell on AWS"""
        if create:
            playbook_cli = PlaybookCLI([
                'ansible-playbook',
                '-i',
                inventory,
                playbook,
                '--key-file',
                key_file,
            ])
            playbook_cli.parse()
            playbook_cli.run()

    @aws.command(name='node')
    @click.option('--create', required=False, is_flag=True,
                  help='Create a new treadmill node',)
    @click.option('--playbook', default='node.yml',
                  help='Playbok file',)
    @click.option('--inventory', default='controller.inventory',
                  help='Inventory file',)
    @click.option('--key-file', default='key.pem',
                  help='AWS ssh pem file',)
    def node(create, playbook, inventory, key_file):
        """Manage treadmill node"""
        if create:
            playbook_cli = PlaybookCLI([
                'ansible-playbook',
                '-i',
                inventory,
                playbook,
                '--key-file',
                key_file,
            ])
            playbook_cli.parse()
            playbook_cli.run()

    del cell
    del node

    return aws
