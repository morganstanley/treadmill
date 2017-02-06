"""Helper tools to manage Treadmill versions."""


import hashlib
import logging
import os
import kazoo

from . import zkutils
from . import zknamespace as z


_LOGGER = logging.getLogger(__name__)


def checksum_dir(path):
    """Calculates checksum of the directory.

    Walks the directory tree and calculate the checksum.
    """

    checksum = hashlib.sha256()

    for root, dirs, files in os.walk(path, topdown=True, followlinks=False):
        try:
            dirs.remove('.git')
        except ValueError:
            pass

        path_len = len(path)
        for filename in sorted(files):
            fullpath = os.path.join(root, filename)
            if os.path.islink(fullpath):
                checksum.update(
                    '{src} -> {dst}'.format(
                        src=fullpath[path_len:],
                        dst=os.readlink(fullpath)
                    )
                )
                # NOTE(boysson): we could os.lstat the link too. Not sure if
                #                this is worth it.

            else:
                stat = os.stat(fullpath)
                checksum.update(
                    '{name!r} {mode!r} {size!r} {mtime!r} {ctime!r}'.format(
                        name=fullpath[path_len:],
                        mode=stat.st_mode,
                        size=stat.st_size,
                        mtime=stat.st_mtime,
                        ctime=stat.st_ctime,
                    )
                )
                # Calculating full checksum on content is slow.
                # with open(fullpath) as f:
                #     checksum.update(f.read())

        for dirname in sorted(dirs):
            fullpath = os.path.join(root, dirname)
            if os.path.islink(fullpath):
                checksum.update(
                    '{src} -> {dst}'.format(
                        src=fullpath[path_len:],
                        dst=os.readlink(fullpath)
                    )
                )

    return checksum


def verify(zkclient, expected, servers):
    """Verifies that version info is up to date."""
    not_up_to_date = []
    for server in servers:
        if not zkclient.exists(z.path.server(server)):
            continue

        version_path = z.path.version(server)
        try:
            version_info = zkutils.get(zkclient, version_path)
            if version_info.get('digest') != expected:
                _LOGGER.debug('not up to date: %s', server)
                not_up_to_date.append(server)
            else:
                _LOGGER.debug('ok: %s', server)

        except kazoo.client.NoNodeError:
            _LOGGER.debug('version info does not exist: %s', server)
            not_up_to_date.append(server)

    return not_up_to_date


def upgrade(zkclient, expected, servers, batch_size, timeout,
            stop_on_error=False, force_upgrade=False):
    """Upgrade all servers in cell, in batches, waiting for success."""

    def _is_alive(server):
        """Check if server is alive."""
        return zkclient.exists(z.path.server(server))

    def _version_ok(server):
        """Check that the version is up to date."""
        if force_upgrade:
            return False

        version_path = z.path.version(server)
        try:
            version_info = zkutils.get(zkclient, version_path)
            version_ok = version_info.get('digest') == expected
            return version_ok
        except kazoo.client.NoNodeError:
            return False

    def _upgrade_ok(server):
        """Check that upgrade succeeded."""
        version_path = z.path.version(server)
        exists = zkutils.exists(zkclient,
                                version_path,
                                timeout)
        if exists:
            version_info = zkutils.get(zkclient, version_path)
            version_ok = version_info.get('digest') == expected
            _LOGGER.info('Version check: %s - %s',
                         server,
                         'ok.' if version_ok else 'fail.')
            return version_ok
        else:
            _LOGGER.info('Failed to start: %s', server)
            return False

    total_failed = []
    for index in range(0, len(servers), batch_size):
        batch = set(servers[index:index + batch_size])
        _LOGGER.info('Processing batch: %r', list(batch))

        up_to_date = set(filter(_version_ok, batch))
        _LOGGER.info('Up to date: %r', list(up_to_date))

        for server in batch - up_to_date:
            version_path = z.path.version(server)
            _LOGGER.info('Upgrading: %s', server)
            zkutils.ensure_deleted(zkclient, version_path)

        running = set(filter(_is_alive, batch))
        _LOGGER.info('Down: %r', list(batch - running))
        failed = [server for server in running if not _upgrade_ok(server)]

        if failed and stop_on_error:
            return failed
        else:
            total_failed.extend(failed)

    return total_failed
