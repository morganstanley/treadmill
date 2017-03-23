"""Simple watchdog system.
"""


import errno
import logging
import os
import re
import stat
import tempfile
import time

from . import fs


_LOGGER = logging.getLogger(__name__)

_DEFAULT_WATCHDOG_TIMEOUT = '30s'


class Watchdog(object):
    """Simple file based watchdog system."""

    WATCHDOG_NAME_RE = re.compile(r'^(?P<name>(?:\w+[#:\.\-@]*)*\w+)$')
    WATCHDOG_DURATION_RE = re.compile(r'^(?P<duration>[0-9]{1,3}[smhd])$')

    def __init__(self, basepath, timeout=_DEFAULT_WATCHDOG_TIMEOUT):
        self.watchdog_path = basepath
        self.timeout = timeout

    def initialize(self):
        """Properly setup an empty watchdog directory.
        """
        for _watchdog, filename, _stat in self._list_gen(self.watchdog_path):
            os.unlink(filename)
        os.chmod(self.watchdog_path, 0o1777)

    def check(self):
        """Check the status of all watchdogs.

        :returns `list`:
            List of `(name, duration, data)` for each failed watchdog.
        """
        curtime = time.time()
        failed_watchdogs = []
        for watchdog, filename, st_info in self._list_gen(self.watchdog_path):
            if curtime < st_info.st_mtime:
                # If the watchdog is set in the future, then service is still
                # alive
                pass

            else:
                # Otherwise, this is a watchdog failure
                _LOGGER.warning('Watchdog failed: %r.', watchdog)
                failed_watchdogs.append((filename, watchdog, st_info.st_mtime))

        # Retreive the payload of failed watchdogs
        if failed_watchdogs:
            failures = []
            for filename, name, failed_at in failed_watchdogs:
                try:
                    with open(filename, 'r') as f:
                        data = f.read()
                except OSError:
                    _LOGGER.exception('Reading watchdog data')
                    data = ''
                failures.append((name, failed_at, data))

            return failures

        else:
            return []

    def create(self, name, timeout=None, content=''):
        """Create a watchdog.

        :param name:
            Name associated with the watchdog
        :type name:
            ``str``
        :param timeout:
            Timeout for the watchdog in the format `[0-9]{1,3}[smhd]`
        :type timeout:
            ``str``
        :param content:
            Content to be recorded with the watchdog
        :type content:
            ``bytes``
        """
        if not self.WATCHDOG_NAME_RE.match(name):
            raise ValueError('Invalid name format: %r' % name)

        if timeout is None:
            timeout = self.timeout
        else:
            if not self.WATCHDOG_DURATION_RE.match(timeout):
                raise ValueError('Invalid timeout duration: %r' % timeout)
        timeout_in_sec = self._duration_to_secs(timeout)

        return self.Lease(self.watchdog_path, name, timeout_in_sec, content)

    class Lease(object):
        """Watchdog Lease object.

        Represent a currently held watchdog lease.
        """

        __slots__ = (
            'content',
            'filename',
            'name',
            'timeout',
        )

        def __init__(self, basedir, name, timeout, content):
            self.name = name
            self.timeout = timeout
            self.content = content
            self.filename = os.path.join(basedir, name)

            _LOGGER.debug('Setting up watchdog: %r', self)
            self._write(timeout_at=time.time() + self.timeout,
                        overwrite=False)

        def __hash__(self):
            return hash(self.filename)

        def __eq__(self, other):
            return self.filename == other.filename

        def _write(self, timeout_at, overwrite=True):
            """Setup the watchdog's lease file."""

            if overwrite or not os.path.exists(self.filename):
                dirname = os.path.dirname(self.filename)
                filename = os.path.basename(self.filename)

                fs.mkdir_safe(dirname)
                with tempfile.NamedTemporaryFile(dir=dirname,
                                                 prefix='.' + filename,
                                                 delete=False,
                                                 mode='w') as tmpfile:
                    os.chmod(tmpfile.name, 0o600)
                    tmpfile.write(self.content)
                    # We have to flush now to make sure utime is the last
                    # operation we do on the file.
                    tmpfile.flush()
                    os.utime(tmpfile.name, (timeout_at, timeout_at))

                os.rename(tmpfile.name, self.filename)

        def heartbeat(self):
            """Renew a watchdog for one timeout."""
            timeout_at = time.time() + self.timeout

            try:
                os.utime(self.filename, (timeout_at, timeout_at))

            except OSError as err:
                if err.errno == errno.ENOENT:
                    _LOGGER.warning('Lost lease file: %r', self.filename)
                    self._write(timeout_at)
                else:
                    raise

        def remove(self):
            """Remove a watchdog."""
            _LOGGER.debug('Clear watchdog: %r:%s', self.name, self.timeout)
            try:
                os.unlink(self.filename)

            except OSError as err:
                if err.errno == errno.ENOENT:
                    _LOGGER.warning('Lost lease file: %r', self.filename)
                else:
                    raise

        def __repr__(self):
            return "<{cls}: {name}:{timeout}>".format(
                cls=self.__class__.__name__,
                name=self.name,
                timeout=self.timeout
            )

    @staticmethod
    def _list_gen(watchdog_path):
        """Generate the list of currently defined watchdogs.

        :returns `list`:
            List of (`name`, `filename`) of defined watchdog.
        """
        # Remove all dotfiles and all non-file
        for watchdog in os.listdir(watchdog_path):
            if watchdog[0] == '.':
                continue

            filename = os.path.join(watchdog_path, watchdog)
            try:
                filestat = os.lstat(filename)
            except os.error:
                continue

            if not stat.S_ISREG(filestat.st_mode):
                continue

            yield (watchdog, filename, filestat)

    @staticmethod
    def _duration_to_secs(duration):
        """Convert all duration specifications into seconds."""
        secs = int(duration[:-1])
        if duration[-1] == 's':
            pass
        elif duration[-1] == 'm':
            secs *= 60
        elif duration[-1] == 'h':
            secs *= 60 * 60
        elif duration[-1] == 'd':
            secs *= 60 * 60 * 24
        else:
            raise ValueError('Invalid duration: %r' % duration)

        return secs
