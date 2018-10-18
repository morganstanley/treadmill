"""Useful utility functions.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import errno
import functools
import io
import json
import logging
import os
import signal
import sys
import time

# Pylint warning re string being deprecated
#
# pylint: disable=W0402
import string

if os.name != 'nt':
    # Pylint warning unable to import because it is on Linux only
    import fcntl    	# pylint: disable=import-error
    import pwd      	# pylint: disable=import-error
    import resource 	# pylint: disable=import-error
else:
    # Pylint warning unable to import because it is on Windows only
    import win32api  # pylint: disable=E0401
    import win32security  # pylint: disable=E0401

# disable standard import "import ipaddress" comes before "import win32api"
import ipaddress  # pylint: disable=C0411
import six

from six.moves import urllib_parse

from treadmill import exc
from treadmill import osnoop


_LOGGER = logging.getLogger(__name__)


_DEFAULT_BASE_ALPHABET = string.digits + string.ascii_lowercase


def ip2int(ip_addr):
    """Converts string IP address representation into integer."""
    i = [int(x) for x in ip_addr.split('.')]
    return (i[0] << 24) | (i[1] << 16) | (i[2] << 8) | i[3]


def int2ip(ip_addr_int32):
    """Converts integer to IP address string."""
    def _int2ip(ip_addr_int32, offset, acc):
        """Shift / recursive conversion of int32 to IP parts."""
        if offset == 0:
            acc.append(str(ip_addr_int32))
        else:
            acc.append(str(ip_addr_int32 >> offset))
            _int2ip(ip_addr_int32 - ((ip_addr_int32 >> offset) << offset),
                    offset - 8, acc)

    acc = []
    _int2ip(ip_addr_int32, 24, acc)
    return '.'.join(acc)


def to_obj(value, name='struct'):
    """Recursively converts dictionary and lists to namedtuples."""
    if isinstance(value, list):
        return [to_obj(item) for item in value]
    elif isinstance(value, dict):
        return collections.namedtuple(name, value.keys())(
            *[to_obj(v, k) for k, v in six.iteritems(value)])
    else:
        return value


def get_iterable(obj):
    """Gets an iterable from either a list or a single value.
    """
    if obj is None:
        return ()

    if (isinstance(obj, collections.Iterable) and
            not isinstance(obj, six.string_types)):
        return obj
    else:
        return (obj,)


def iterable_to_stream(iterable, buffer_size=io.DEFAULT_BUFFER_SIZE):
    """Convert an iterable into a `io.BufferedReader` file like object.
    """
    class IterRawStream(io.RawIOBase):
        """io stream class wrapping an iterator.
        """

        __slots__ = (
            '_remain',
        )

        def __init__(self):
            super(IterRawStream, self).__init__()
            self._remain = None

        def readable(self):
            return True

        def readinto(self, buff):
            """Read from the iterator into a buffer (in place).
            """
            try:
                max_len = len(buff)
                chunk = self._remain or next(iterable)
                output, self._remain = chunk[:max_len], chunk[max_len:]
                # Update target buffer in place.
                buff[:len(output)] = output

                return len(output)

            except StopIteration:
                return 0

    return io.BufferedReader(
        raw=IterRawStream(),
        buffer_size=buffer_size
    )


def sys_exit(code):
    """Exit using os._exit, bypassing any on_exit code.

    Should be used in a child process after fork().
    """
    # We need access to "private" member _exit
    # pylint: disable=W0212
    _LOGGER.debug('os._exit, rc: %d', code)
    os._exit(code)


def hashcmp(file1, file2):
    """Compare two files based on sha1 hash value."""

    # TODO: this function seem to be unused. keeping for now, will need add
    #       assert later and see what plugin might break.
    import hashlib

    sha1 = hashlib.sha1()
    sha2 = hashlib.sha1()

    with io.open(file1, 'rb') as f:
        data = f.read()
        sha1.update(data)

    with io.open(file2, 'rb') as f:
        data = f.read()
        sha2.update(data)

    return sha1.hexdigest() == sha2.hexdigest()


def rootdir():
    """Returns install root of the Treadmill framework."""
    if 'TREADMILL' in os.environ:
        return os.environ['TREADMILL']
    else:
        raise Exception('Must have TREADMILL env variable.')


def touch(filename):
    """'Touch' a filename.
    """
    try:
        os.utime(filename, None)
    except OSError as err:
        if err.errno == errno.ENOENT:
            io.open(filename, 'wb').close()
        else:
            raise


class FileLock:
    """Utility file based lock."""

    def __init__(self, filename):
        self.fd = io.open(filename + '.lock', 'w')

    def __enter__(self):
        fcntl.flock(self.fd, fcntl.LOCK_EX)

    def __exit__(self, type_unused, value_unused, traceback_unused):
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        self.fd.close()


def cpu_units(value):
    """Converts CPU string into numeric in BMIPS"""
    norm = str(value).upper().strip()
    if norm.endswith('%'):
        return int(norm[:-1])
    else:
        return int(norm)


_SIZE_SCALE = {x[1]: x[0]
               for x in enumerate(['B', 'K', 'M', 'G', 'T',
                                   'P', 'E', 'Z', 'Y'])}


def size_to_bytes(size):
    """Convert a human friendly size string into a size in bytes.

    Properly handles input values with suffix (M, G, T, P, E, Z, Y) and an
    optional 'B' suffix modifier (MB, GB, TB, PB, EB, ZB, YB).

    If size is an integer, it is assumed to be in bytes already.

    :param size:
        `size` optionally followed by a suffix.
    :type size:
        ``str`` | ``int``
    :returns:
        (``int``) -- `size` in bytes

    *Examples*:

    .. testsetup::

        from treadmill.utils import size_to_bytes

    >>> size_to_bytes('1KB')
    1000
    >>> size_to_bytes('1K')
    1024
    """
    if isinstance(size, six.string_types):
        size = size.upper().strip()
        unit = 1024
        if size[-1] == 'B':
            unit = 1000
            size = size[:-1]
        if size[-1] in _SIZE_SCALE:
            return int(size[:-1]) * pow(unit, _SIZE_SCALE[size[-1]])
        else:
            return int(size)
    else:
        return int(size)


def kilobytes(value):
    """Converts values with M/K/G suffix into numeric in Kbytes.

    The following are valid strings:
    10K
    10M
    10G
    10 (default kb)
    """
    norm = str(value).upper().strip()
    if norm == '0':
        return 0

    if norm[-1] not in _SIZE_SCALE:
        # Shortcut since this function assumes unsuffixed into is already in
        # Kbytes
        _LOGGER.error('Invalid (unitless) value: %s', value)
        raise Exception('Invalid (unitless) value: ' + str(value))

    return size_to_bytes(value) // 1024


def megabytes(value):
    """Converts values with M/K/G suffix info numeric in Mbytes"""
    return kilobytes(value) // 1024


def reboot_schedule(value):
    """Parse reboot schedule spec.
    """
    days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

    # pylint: disable=invalid-name
    def parse_tod(tod):
        """Parse time of day."""
        h, m, s = [int(x) for x in tod.split(':')]

        if not 0 <= h <= 23:
            raise ValueError('Hour out of bounds')
        if not 0 <= m <= 59:
            raise ValueError('Minute out of bounds')
        if not 0 <= s <= 59:
            raise ValueError('Second out of bounds')

        return (h, m, s)

    def parse_entry(entry):
        """Parse day specification."""
        if entry in days:
            return (days.index(entry), (23, 59, 59))
        else:
            day, tod = entry.split('/')
            return (days.index(day), parse_tod(tod))

    return {
        day: time
        for x in value.split(',')
        for day, time in [parse_entry(x)]
    }


def validate(struct, schema):
    """Validate dictionary required fields.

    The schema is a list of tuples (field, required, field_type). For each
    tuple the function will check that required field is present and that it is
    of expected type. If not required field is missing, it will be initialize
    with the type constructor.
    """
    if not isinstance(struct, dict):
        raise exc.InvalidInputError(struct, 'Expected dict.')

    for field, required, ftype in schema:
        if field not in struct:
            if required:
                raise exc.InvalidInputError(
                    struct, 'Required field: %s' % field)
            else:
                continue

        # Make str type validation work across Py2 and Py3
        if ftype is str:
            ftype = six.string_types

        if not isinstance(struct[field], ftype):
            raise exc.InvalidInputError(
                struct, 'Invalid type for %s, expected: %s, got: %s' %
                (field, str(ftype), type(struct[field])))


_TIME_SCALE = {'S': 1,
               'M': 60,
               'H': 60 * 60,
               'D': 60 * 60 * 24}


def to_seconds(value):
    """Converts values with s/m/d suffix into numeric in seconds."""
    norm = str(value).upper().strip()
    if norm[-1] not in _TIME_SCALE:
        _LOGGER.error('Invalid (unitless) interval: %s', value)
        raise Exception('Invalid (unitless) interval: ' + str(value))

    return int(norm[0:-1]) * _TIME_SCALE[norm[-1]]


def bytes_to_readable(num, power='M'):
    """Converts numerical value into human readable memory value."""
    powers = ['B', 'K', 'M', 'G', 'T']
    # 4 digits
    while num >= 1000:
        num /= 1024.0
        next_power_idx = powers.index(power) + 1
        if next_power_idx == len(powers):
            break
        power = powers[next_power_idx]
    return '%.1f%s' % (num, power)


def find_in_path(prog):
    """Search for application in system path and returns the full path."""
    if os.path.isabs(prog):
        return prog

    for path in os.environ.get('PATH', '').split(os.pathsep):
        fullpath = os.path.join(path, prog)
        if os.path.exists(fullpath) and os.access(fullpath, os.X_OK):
            return fullpath

    return prog


def tail_stream(stream, nlines=10):
    """Returns last N lines from the io object (file or io.string).
    """
    # Seek to eof, backtrack 1024 or to the beginning, return last
    # N lines.
    stream.seek(0, 2)
    fsize = stream.tell()
    stream.seek(max(0, fsize - 1024), 0)
    lines = stream.readlines()
    return lines[-nlines:]


def tail(filename, nlines=10):
    """Retuns last N lines from the file."""
    try:
        with io.open(filename) as f:
            return tail_stream(f, nlines=nlines)
    except Exception:  # pylint: disable=W0703
        _LOGGER.exception('Cannot open %r for reading.', filename)
        return []


def strftime_utc(epoch):
    """Convert seconds from epoch into UTC time string."""
    return time.strftime('%a, %d %b %Y %H:%M:%S+0000', time.gmtime(epoch))


def to_base_n(num, base=None, alphabet=None):
    """Encode a number in base X using a given alphabet

    :param int number:
        Number to encode
    :param int base:
        Length of the base to use
    :param str alphabet:
        The alphabet to use for encoding
    """
    if alphabet is None:
        alphabet = _DEFAULT_BASE_ALPHABET
    if base is None:
        base = len(alphabet)
    if not 0 <= base <= len(alphabet):
        raise ValueError('Invalid base length: %s' % base)

    if num == 0:
        return alphabet[0]

    arr = []
    while num:
        rem = num % base
        num = num // base
        arr.append(alphabet[rem])
    arr.reverse()
    return ''.join(arr)


def from_base_n(base_num, base=None, alphabet=None):
    """Decode a Base X encoded string into the number

    :param str base_num:
        Number encoded in the given base
    :param int base:
        Length of the base to use
    :param str alphabet:
        The alphabet to use for encoding
    """
    if alphabet is None:
        alphabet = _DEFAULT_BASE_ALPHABET
    if base is None:
        base = len(alphabet)
    if not 0 <= base <= len(alphabet):
        raise ValueError('Invalid base length: %s' % base)

    strlen = len(base_num)
    num = 0

    idx = 0
    for char in base_num:
        power = (strlen - (idx + 1))
        num += alphabet.index(char) * (base ** power)
        idx += 1

    return num


@osnoop.windows
def report_ready(notification_fd=None):
    """Reports the service as ready for s6-svwait -U."""
    if notification_fd is None:
        try:
            with io.open('notification-fd') as f:
                notification_fd = int(f.readline())
        except (IOError, OSError):
            _LOGGER.exception('Cannot read notification-fd')
            return

    try:
        os.write(notification_fd, b'ready\n')
        os.close(notification_fd)
    except OSError:
        _LOGGER.warning('notification-fd %s does not exist.', notification_fd)


@osnoop.windows
def drop_privileges(uid_name='nobody'):
    """Drop root privileges."""
    if os.getuid() != 0:
        # We're not root, nothing to do.
        return

    # Get the uid/gid from the name
    (running_uid, _gid) = get_uid_gid(uid_name)

    # Remove group privileges
    os.setgroups([])

    # Try setting the new uid/gid
    os.setuid(running_uid)

    # Ensure a very conservative umask
    os.umask(0o77)

    # TODO: probably redundant, as it will not have access to the
    #                cred cache anyway.
    os.environ['KRB5CCNAME'] = 'FILE:/no_such_krbcc'


def _setup_sigs():
    sigs = {}
    for signame, sigval in vars(signal).items():
        # We want all signal.SIG* but not signal.SIG_*
        if (not signame.startswith('SIG')) or signame.startswith('SIG_'):
            continue

        sigs.setdefault(sigval, [str(sigval)]).append(signame)

    return {
        sigval: '/'.join(signames)
        for sigval, signames in sigs.items()
    }


_SIG2NAME = _setup_sigs()
del _setup_sigs


def cidr_range(start_ip, end_ip):
    """
    Generate cidr coverage of the ip range
    :param start_ip: number or string or IPv4Address
    :param end_ip: number or string or IPv4Address
    """
    if isinstance(start_ip, str):
        start_ip = str(start_ip)
    if isinstance(end_ip, str):
        end_ip = str(end_ip)
    return list(
        ipaddress.summarize_address_range(
            ipaddress.IPv4Address(start_ip),
            ipaddress.IPv4Address(end_ip)
        )
    )


def signal2name(num):
    """Convert signal number to signal name."""
    return _SIG2NAME.get(num, num)


def term_signal():
    """Gets the term signal for the os."""
    if os.name == 'nt':
        return signal.SIGBREAK
    else:
        return signal.SIGTERM


def make_signal_flag(*signals):
    """Return a flag that will be set when process is signaled."""
    _LOGGER.info('Configuring signal flag: %r', signals)
    signalled = set()

    def _handler(signum, _frame):
        """Signal handler."""
        signalled.add(signum)

    for signum in signals:
        signal.signal(signum, _handler)

    return signalled


def compose(*funcs):
    """Compose functions.
    """
    return lambda x: six.moves.reduce(lambda v, f: f(v), reversed(funcs), x)


def equals_list2dict(equals_list):
    """Converts an array of key/values seperated by = to dict"""
    return dict(entry.split('=') for entry in equals_list)


def encode_uri_parts(path):
    """Encode URI path components"""
    return '/'.join([urllib_parse.quote(part) for part in path.split('/')])


def is_root():
    """Gets whether the current user is root"""
    if os.name == 'nt':
        sid = win32security.CreateWellKnownSid(win32security.WinLocalSystemSid,
                                               None)
        return win32security.CheckTokenMembership(None, sid)
    else:
        return os.geteuid() == 0


def get_current_username():
    """Returns the current user name"""
    if os.name == 'nt':
        return win32api.GetUserName()
    else:
        return get_username(os.getuid())


# List of signals that can be manipulated
if sys.platform == 'win32':
    _SIGNALS = {signal.SIGABRT, signal.SIGFPE, signal.SIGILL, signal.SIGINT,
                signal.SIGSEGV, signal.SIGTERM, signal.SIGBREAK}
else:
    _SIGNALS = (set(range(1, signal.NSIG)) -
                {signal.SIGKILL, signal.SIGSTOP, 32, 33})


@osnoop.windows
def get_ulimit(u_type):
    """get ulimit value
    resource type name nofile => RLIMIT_NOFILE
    return tuple of (soft_limit, hard_limit)
    """
    type_name = 'RLIMIT_{}'.format(u_type.upper())
    return resource.getrlimit(getattr(resource, type_name))


@osnoop.windows
def closefrom(firstfd):
    """Close all file descriptors from `firstfd` on.
    """
    try:
        # Look in proc for all open filedescriptors
        maxfd = int(os.listdir('/proc/self/fd')[-1])
    except (OSError, IndexError):
        # fallback to the hardlimit to max filedescriptors.
        maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]

    os.closerange(firstfd, maxfd)


def restore_signals():
    """Reset the default behavior to all signals.
    """
    for i in _SIGNALS:
        signal.signal(i, signal.SIG_DFL)


@osnoop.windows
def sane_execvp(filename, args, close_fds=True, signals=True):
    """Execute a new program with sanitized environment.
    """
    if six.PY2:
        # Work around Python2 leaking filedescriptors.
        if close_fds:
            closefrom(3)
    if signals:
        restore_signals()
    os.execvp(filename, args)


def exit_on_unhandled(func):
    """Decorator to exit thread on unhandled exception."""
    @functools.wraps(func)
    def _wrap(*args, **kwargs):
        """Wraps function to exit on unhandled exception."""
        try:
            return func(*args, **kwargs)
        except Exception:  # pylint: disable=W0703
            _LOGGER.exception('Unhandled exception - exiting.')
            sys_exit(-1)

    return _wrap


def json_genencode(obj, indent=None):
    """JSON encoder that returns an UTF-8 JSON data generator.

    :returns
        ``generator`` - Generator of JSON unicode data chunks.
    """
    encoder = json.JSONEncoder(
        skipkeys=False,
        ensure_ascii=True,
        check_circular=True,
        allow_nan=True,
        indent=indent,
        separators=None,
        default=None,
    )

    return (
        six.text_type(chunk)
        for chunk in encoder.iterencode(obj)
    )


def parse_mask(value, mask_enum):
    """Parse a mask into indivitual mask values from enum.

    :params ``int`` value:
        (Combined) mask value.
    :params ``enum.IntEnum`` mask_enum:
        Enum of all possible mask values.
    :returns:
        ``list`` - List of enum values and optional remainder.
    """
    masks = []
    for mask in mask_enum:
        if value & mask:
            masks.append(mask.name)
            value ^= mask
    if value:
        masks.append(hex(value))

    return masks


def iter_sep(iterable, separator):
    """Take an iterator and returns an new iterator over all the same values
    separated by `separator`.

    :params ``Iterator`` iterator:
        Iterator over something.
    :params separator:
        Value returned in between each value of the iterator.
    :returns:
        ``Iterator`` - Values from `iterator` separated by `separator`.
    """
    for i in iterable:
        yield i
        yield separator


def get_uid_gid(username):
    """Get linux uid/gid from username
    """
    user_pw = pwd.getpwnam(username)
    return (user_pw.pw_uid, user_pw.pw_gid)


def get_username(uid):
    """Get linux username from uid
    """
    return pwd.getpwuid(uid).pw_name


def get_usershell(username):
    """Get linux user shell
    """
    user_pw = pwd.getpwnam(username)
    return user_pw.pw_shell


def get_userhome(username):
    """Get linux user home dir
    """
    user_pw = pwd.getpwnam(username)
    user_pw = pwd.getpwnam(username)
    return user_pw.pw_dir


__all__ = [
    'bytes_to_readable',
    'cidr_range',
    'closefrom',
    'compose',
    'cpu_units',
    'drop_privileges',
    'encode_uri_parts',
    'equals_list2dict',
    'exit_on_unhandled',
    'find_in_path',
    'from_base_n',
    'get_current_username',
    'get_iterable',
    'hashcmp',
    'int2ip',
    'ip2int',
    'is_root',
    'iterable_to_stream',
    'iter_sep',
    'json_genencode',
    'kilobytes',
    'make_signal_flag',
    'megabytes',
    'parse_mask',
    'reboot_schedule',
    'report_ready',
    'restore_signals',
    'rootdir',
    'sane_execvp',
    'signal2name',
    'size_to_bytes',
    'strftime_utc',
    'sys_exit',
    'tail',
    'tail_stream',
    'term_signal',
    'touch',
    'to_base_n',
    'to_obj',
    'to_seconds',
    'validate',
]
