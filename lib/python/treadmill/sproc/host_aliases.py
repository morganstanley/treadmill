"""Treadmill /etc/hosts manager."""


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import glob
import errno
import socket
import time
import logging

import click
import six

from treadmill import dirwatch


_LOGGER = logging.getLogger(__name__)

# In case there is DNS resolution error, retry every 10sec.
_DNS_RETRY_INTERVAL = 10 * 1000


def _canonical(hostname):
    """Return IP and canonical name given the hostname."""
    _LOGGER.info('Resolving: %s', hostname)
    ipaddr = socket.gethostbyname(hostname)
    fqdn = socket.getfqdn(hostname)
    _LOGGER.info('Resolved: ipaddr: %s, fqdn: %s', ipaddr, fqdn)
    return ipaddr, fqdn


def _resolve(path, aliases):
    """Resolve alias symlink."""
    if not os.path.islink(path):
        _LOGGER.info('not a symlink %s:', path)
        return

    alias = os.path.basename(path)

    try:
        hostname = os.readlink(path)
        _LOGGER.info('Added alias: %s - %r', alias, hostname)
        aliases[alias] = hostname
    except OSError as err:
        if err.errno == errno.ENOENT:
            if alias in aliases:
                del aliases[alias]


def _generate(aliases, original, dest, retry):
    """Generate target hosts file."""
    _LOGGER.info('Generating: %s', dest)
    retry.clear()
    with io.open(dest, 'w') as f:
        f.write(original)
        for alias, hostname in six.iteritems(aliases):
            try:
                ipaddr, fqdn = _canonical(hostname)
                _LOGGER.info('alias: %s %s %s', ipaddr, fqdn, alias)
                f.write('{ipaddr} {fqdn} {alias}\n'.format(
                    ipaddr=ipaddr,
                    fqdn=fqdn,
                    alias=alias
                ))
            except socket.gaierror as err:
                _LOGGER.info(
                    'Unable to resolve hostname: %s, errno: %s',
                    hostname,
                    err.errno
                )
                retry.add(1)
            except Exception:  # pylint: disable=W0703
                _LOGGER.warning('Invalid alias: %s, %s', alias, hostname)


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--aliases-dir', type=click.Path(exists=True),
                  required=True)
    @click.argument('source', type=click.Path(exists=True, readable=True))
    @click.argument('dest')
    def hosts_aliases_cmd(aliases_dir, source, dest):
        """Manage /etc/hosts aliases."""
        aliases = {}
        retry = set()
        with io.open(source, 'r') as fd:
            original = fd.read()

        def _on_created(path):
            """Callback invoked when new alias is created."""
            if os.path.basename(path).startswith('^'):
                return

            _resolve(path, aliases)
            _generate(aliases, original, dest, retry)

        def _on_deleted(path):
            """Callback invoked when alias is removed."""
            _LOGGER.info('Alias removed: %s', path)
            alias = os.path.basename(path)
            if alias in aliases:
                del aliases[alias]

            _generate(aliases, original, dest, retry)

        watcher = dirwatch.DirWatcher(aliases_dir)
        watcher.on_created = _on_created
        watcher.on_deleted = _on_deleted

        existing = glob.glob(os.path.join(aliases_dir, '*'))
        for path in existing:
            if os.path.basename(path).startswith('^'):
                os.unlink(path)
                continue

            _resolve(path, aliases)

        _generate(aliases, original, dest, retry)

        last_retry = 0
        while True:
            if watcher.wait_for_events(timeout=100):
                watcher.process_events(max_events=100)
                last_retry = time.time()

            if retry and (time.time() > (last_retry + _DNS_RETRY_INTERVAL)):
                _generate(aliases, original, dest, retry)
                last_retry = time.time()

    return hosts_aliases_cmd
