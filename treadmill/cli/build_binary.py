"""Treadmill build binary CLI.
"""
import click
import subprocess

import logging

_LOGGER = logging.getLogger(__name__)


def init():
    """Return top level command handler."""

    @click.option('--release-message', '-m', help='Release message',
                  default='')
    @click.option('--release-tag', '-t', help='Release tag', default='')
    @click.option('--source', '-s', help='Treadmill source directory path',
                  required=True)
    @click.command(name='build-binary')
    def build_binary(release_message, release_tag, source):
        """Build treadmill binary and RPM
        """
        subprocess.call([
            'bash',
            source + '/build_binary.sh',
            release_message,
            release_tag,
        ])

    return build_binary
