"""Plugin manager."""

import logging
import tempfile
import traceback

import click

from stevedore import extension


_EXTENSION_MANAGERS = {}

_DRIVER_MANAGERS = {}

_LOGGER = logging.getLogger(__name__)


def extensions(namespace, invoke_on_load=False, invoke_args=None,
               invoke_kwds=None, cli=False):
    """Returns extention manager for given namespace."""
    # pylint: disable=W0602
    global _EXTENSION_MANAGERS

    if invoke_args is None:
        invoke_args = ()
    if invoke_kwds is None:
        invoke_kwds = {}

    def _extensions():
        """Create or return extension manager lazily."""

        # TODO: Does it need to be stored, or can be constructed every time?
        if namespace not in _EXTENSION_MANAGERS:

            log = log_extension_failure
            if cli is True:
                log = cli_extension_failure

            _EXTENSION_MANAGERS[namespace] = extension.ExtensionManager(
                namespace=namespace,
                invoke_on_load=invoke_on_load,
                invoke_args=invoke_args,
                invoke_kwds=invoke_kwds,
                propagate_map_exceptions=True,
                on_load_failure_callback=log
            )

        return _EXTENSION_MANAGERS[namespace]

    return _extensions


def cli_extension_failure(_manager, entrypoint, _exception):
    """Logs errors for stevedore extensions."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        traceback.print_exc(file=f)
        click.echo('Error loading %r [ %s ]' % (str(entrypoint), f.name),
                   err=True)


def log_extension_failure(_manager, entrypoint, exception):
    """Logs errors for stevedore extensions."""
    _LOGGER.error('Error loading %r.', str(entrypoint), exc_info=exception)
