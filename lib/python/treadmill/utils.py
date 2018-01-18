"""Useful utility functions.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import datetime
import errno
import functools
import hashlib
import io
import json
import locale
import logging
import os
import signal
import stat
import sys
import tempfile
import time

# Pylint warning re string being deprecated
#
# pylint: disable=W0402
import string

if os.name != 'nt':
    import fcntl
    import pwd
    import resource
else:
    # Pylint warning unable to import because it is on Windows only
    import win32api  # pylint: disable=E0401
    import win32con  # pylint: disable=E0401
    import win32security  # pylint: disable=E0401

# disable standard import "import ipaddress" comes before "import win32api"
import ipaddress  # pylint: disable=C0411
import jinja2
import six

from six.moves import urllib_parse

from treadmill import exc
from treadmill import osnoop


_LOGGER = logging.getLogger(__name__)

JINJA2_ENV = jinja2.Environment(loader=jinja2.PackageLoader(__name__))

EXEC_MODE = (stat.S_IRUSR |
             stat.S_IRGRP |
             stat.S_IROTH |
             stat.S_IWUSR |
             stat.S_IXUSR |
             stat.S_IXGRP |
             stat.S_IXOTH)

_DEFAULT_BASE_ALPHABET = string.digits + string.ascii_lowercase


def generate_template(templatename, **kwargs):
    """This renders a JINJA template as a generator.

    The templates exist in our lib/python/treadmill/templates directory.

    :param ``str`` templatename:
        The name of the template file.
    :param ``dict`` kwargs:
        key/value passed into the template.
    """
    template = JINJA2_ENV.get_template(templatename)
    return template.generate(**kwargs)


def create_script(filename, templatename, mode=EXEC_MODE, **kwargs):
    """This Creates a file from a JINJA template.

    The templates exist in our lib/python/treadmill/templates directory.

    :param ``str`` filename:
        Name of the file to generate.
    :param ``str`` templatename:
        The name of the template file.
    :param ``int`` mode:
        The mode for the file (Defaults to +x).
    :param ``dict`` kwargs:
        key/value passed into the template.
    """
    filepath = os.path.dirname(filename)
    with tempfile.NamedTemporaryFile(dir=filepath,
                                     delete=False,
                                     mode='w') as f:
        for data in generate_template(templatename, **kwargs):
            f.write(data)
        if os.name == 'posix':
            # cast to int required in order for default EXEC_MODE to work
            os.fchmod(f.fileno(), int(mode))
    if sys.version_info[0] < 3:
        # TODO: os.rename cannot replace on windows
        # (use os.replace in python 3.4)
        # copied from fs as utils cannot have this dependency
        if os.name == 'nt':
            win32api.MoveFileEx(f.name, filename,
                                win32con.MOVEFILE_REPLACE_EXISTING)
        else:
            os.rename(f.name, filename)
    else:
        os.replace(f.name, filename)


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


class FileLock(object):
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

    The reboot schedule format is list of weekdays when reboot can
    happen. For example "sat,sun" would mean reboot on weekends.
    """
    days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

    return [days.index(d) for d in value.lower().split(',')]


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


def cpu_to_readable(num):
    """Converts CPU % into readable number."""
    # TODO: Move this to CLI initialization
    if os.name == 'posix':
        locale.setlocale(locale.LC_ALL, ('en_US', sys.getdefaultencoding()))
    else:
        locale.setlocale(locale.LC_ALL, '')

    return locale.format('%d', num, grouping=True)


def cpu_to_cores_readable(num):
    """Converts CPU % into number of abstract cores."""
    # TODO: Move this to CLI initialization
    if os.name == 'posix':
        locale.setlocale(locale.LC_ALL, ('en_US', sys.getdefaultencoding()))
    else:
        locale.setlocale(locale.LC_ALL, '')

    return locale.format('%.2f', num / 100.0, grouping=True)


def ratio_to_readable(value):
    """Converts ratio to human readable percentage."""
    return '%.1f' % (value / 100.0)


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


def datetime_utcnow():
    """Wrapper for datetime.datetime.utcnow for testability."""
    return datetime.datetime.utcnow()


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
def report_ready():
    """Reports the service as ready for s6-svwait -U."""
    try:
        with io.open('notification-fd') as f:
            try:
                fd = int(f.readline())
                os.write(fd, b'ready\n')
                os.close(fd)
            except OSError:
                _LOGGER.exception('Cannot read notification-fd')
    except IOError:
        _LOGGER.warning('notification-fd does not exist.')


@osnoop.windows
def drop_privileges(uid_name='nobody'):
    """Drop root privileges."""
    if os.getuid() != 0:
        # We're not root, nothing to do.
        return

    # Get the uid/gid from the name
    running_uid = pwd.getpwnam(uid_name).pw_uid

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


# R0912(too-many-branches): Too many branches (13/12)
# pylint: disable=R0912
def which(cmd, mode=os.F_OK | os.X_OK, path=None):
    """TODO: This function has been copied from the shutil package shipped with
    python 3.4.4. This func has to be deleted once we've upgraded to python 3.

    Given a command, mode, and a PATH string, return the path which
    conforms to the given mode on the PATH, or None if there is no such
    file.

    `mode` defaults to os.F_OK | os.X_OK. `path` defaults to the result
    of os.environ.get('PATH'), or can be overridden with a custom search
    path.

    """
    # Check that a given file can be accessed with the correct mode.
    # Additionally check that `file` is not a directory, as on Windows
    # directories pass the os.access check.
    def _access_check(filename, mode):
        return (os.path.exists(filename) and
                os.access(filename, mode) and
                not os.path.isdir(filename))

    # If we're given a path with a directory part, look it up directly rather
    # than referring to PATH directories. This includes checking relative to
    # the current directory, e.g. ./script
    if os.path.dirname(cmd):
        if _access_check(cmd, mode):
            return cmd
        return None

    if path is None:
        path = os.environ.get('PATH', os.defpath)
    if not path:
        return None
    path = path.split(os.pathsep)

    if sys.platform == 'win32':
        # The current directory takes precedence on Windows.
        if os.curdir not in path:
            path.insert(0, os.curdir)

        # PATHEXT is necessary to check on Windows.
        pathext = os.environ.get('PATHEXT', '').split(os.pathsep)
        # See if the given file matches any of the expected path extensions.
        # This will allow us to short circuit when given "python.exe".
        # If it does match, only test that one, otherwise we have to try
        # others.
        if any(cmd.lower().endswith(ext.lower()) for ext in pathext):
            files = [cmd]
        else:
            files = [cmd + ext for ext in pathext]
    else:
        # On other platforms you don't have things like PATHEXT to tell you
        # what file suffixes are executable, so just pass on cmd as-is.
        files = [cmd]

    seen = set()
    for dir_ in path:
        normdir = os.path.normcase(dir_)
        if normdir not in seen:
            seen.add(normdir)
            for thefile in files:
                name = os.path.join(dir_, thefile)
                if _access_check(name, mode):
                    return name
    return None


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
        return pwd.getpwuid(os.getuid()).pw_name


# List of signals that can be manipulated
if sys.platform == 'win32':
    _SIGNALS = {signal.SIGABRT, signal.SIGFPE, signal.SIGILL, signal.SIGINT,
                signal.SIGSEGV, signal.SIGTERM, signal.SIGBREAK}
else:
    _SIGNALS = (set(range(1, signal.NSIG)) -
                {signal.SIGKILL, signal.SIGSTOP, 32, 33})


@osnoop.windows
def closefrom(firstfd=3):
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
