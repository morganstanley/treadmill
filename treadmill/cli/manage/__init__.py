"""Entry point for treadmill manage ecosystem"""
import pkgutil
import click
from treadmill import cli

__path__ = pkgutil.extend_path(__path__, __name__)


def init():
    """Return top level command handler."""

    @click.group(cls=cli.make_multi_command('treadmill.cli.manage'))
    def manage():
        """Manage applications."""
        pass

    return manage
