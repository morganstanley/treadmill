"""Safely invoke external binaries.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import functools
import io
import json

import six

if six.PY2 and os.name == 'posix':
    # pylint: disable=import-error
    import subprocess32 as subprocess
    from subprocess32 import CalledProcessError
else:
    import subprocess
    from subprocess import CalledProcessError

from treadmill import plugin_manager
from treadmill import utils


_LOGGER = logging.getLogger(__name__)

_EXECUTABLES = None
_CLOSE_FDS = os.name != 'nt'


class CommandAliasError(Exception):
    """Error raised if alises can't be resolved.
    """


def load_aliases(aliases_path):
    """Load aliases from file."""
    global _EXECUTABLES  # pylint: disable=W0603
    with io.open(aliases_path) as f:
        _EXECUTABLES = json.loads(f.read())


def load_packages(packages, lazy=True):
    """Laze load aliases from packages.

    Aliases will not be resolved.
    """
    exes = {}
    for name in packages:
        alias_mod = plugin_manager.load('treadmill.bootstrap', name)
        exes.update(getattr(alias_mod, 'ALIASES'))

    tm = os.environ.get('TREADMILL')
    if tm is not None:
        exes['treadmill'] = tm

    global _EXECUTABLES  # pylint: disable=W0603
    _EXECUTABLES = exes

    if not lazy:
        resolved = {path: resolve(path) for path in _EXECUTABLES}
        _EXECUTABLES = resolved


def get_aliases():
    """Load aliases of external binaries that can invoked."""
    global _EXECUTABLES  # pylint: disable=W0603
    return _EXECUTABLES


def _check(path):
    """Check that path exists and is executable."""
    if path is None:
        return False

    if path.endswith('.so') and (path.find('$ISA') >= 0 or
                                 path.find('$LIB') >= 0):
        # TODO: not sure how to handle $LIB and $ISA for now.
        return True
    else:
        return os.access(path, os.X_OK)


@functools.lru_cache(maxsize=256)
def resolve(exe):
    """Resolve logical name to full path."""
    if os.path.isabs(exe):
        return exe

    executables = get_aliases()

    if not executables.get(exe):
        _LOGGER.debug('Not in aliases: %s', exe)
        return None

    if callable(executables[exe]):
        safe_exe = executables[exe](exe)
    else:
        safe_exe = executables[exe]

    if isinstance(safe_exe, list):
        for choice in safe_exe:
            choice = os.path.normpath(choice)
            if _check(choice):
                return choice
        _LOGGER.debug('Cannot resolve: %s', exe)
        return None
    else:
        safe_exe = os.path.normpath(safe_exe)
        if not _check(safe_exe):
            _LOGGER.debug('Command not found: %s, %s', exe, safe_exe)
            return None

    return safe_exe


def _resolve(exe):
    """Resolve alias, raise exception if not found."""
    resolved = resolve(exe)
    if not resolved:
        raise CommandAliasError('Unable to resolve: {}'.format(exe))
    return resolved


def _alias_command(cmdline):
    """Checks that the command line is in the aliases."""
    safe_cmdline = list(cmdline)
    safe_cmdline.insert(0, _resolve(safe_cmdline.pop(0)))
    return safe_cmdline


def check_call(cmdline, environ=(), runas=None, **kwargs):
    """Runs command wrapping subprocess.check_call.

    :param cmdline:
        Command to run
    :type cmdline:
        ``list``
    :param environ:
        *optional* Environ variable to set prior to running the command
    :type environ:
        ``dict``
    :param runas:
        *optional* Run as user.
    :type runas:
        ``str``
    """
    _LOGGER.debug('check_call environ: %r, runas: %r, %r',
                  environ, runas, cmdline)

    args = _alias_command(cmdline)
    if runas:
        s6_setguid = _resolve('s6_setuidgid')
        args = [s6_setguid, runas] + args

    # Setup a copy of the environ with the provided overrides
    cmd_environ = dict(os.environ.items())
    cmd_environ.update(environ)

    try:
        rc = subprocess.check_call(args, close_fds=_CLOSE_FDS, env=cmd_environ,
                                   **kwargs)
        _LOGGER.debug('Finished, rc: %d', rc)
        return rc
    except CalledProcessError as exc:
        _LOGGER.error('Command failed: rc:%d', exc.returncode)
        raise


def check_output(cmdline, environ=(), **kwargs):
    """Runs command wrapping subprocess.check_output.

    :param cmdline:
        Command to run
    :type cmdline:
        ``list``
    :param environ:
        *optional* Environ variable to set prior to running the command
    :type environ:
        ``dict``
    """
    _LOGGER.debug('check_output environ: %r, %r', environ, cmdline)
    args = _alias_command(cmdline)

    # Setup a copy of the environ with the provided overrides
    cmd_environ = dict(os.environ.items())
    cmd_environ.update(environ)

    try:
        res = subprocess.check_output(args,
                                      close_fds=_CLOSE_FDS,
                                      env=cmd_environ,
                                      **kwargs)

        _LOGGER.debug('Finished.')
    except CalledProcessError as exc:
        _LOGGER.error('Command failed: rc:%d: %s', exc.returncode, exc.output)
        raise

    # Decode output back into unicode
    res = res.decode()

    return res


def call(cmdline, environ=(), **kwargs):
    """Runs command wrapping subprocess.call.

    :param cmdline:
        Command to run
    :type cmdline:
        ``list``
    :param environ:
        *optional* Environ variable to set prior to running the command
    :type environ:
        ``dict``
    """
    _LOGGER.debug('run: %r', cmdline)
    args = _alias_command(cmdline)

    # Setup a copy of the environ with the provided overrides
    cmd_environ = dict(os.environ.items())
    cmd_environ.update(environ)

    rc = subprocess.call(args, close_fds=_CLOSE_FDS, env=cmd_environ, **kwargs)

    _LOGGER.debug('Finished, rc: %d', rc)
    return rc


def invoke(cmd, cmd_input=None, use_except=False, **environ):
    """Runs command and return return code and output.

    Allows passing some input and/or setting all keyword arguments as environ
    variables.

    :param cmd:
        Command to run
    :type cmd:
        ``list``
    :param cmd_input:
        *optional* Provide some input to be passed to the command's STDIN
    :type cmd_input:
        ``str``
    :param environ:
        Environ variable to set prior to running the command
    :type environ:
        ``dict``
    :returns:
        (``(int, str)``) -- Return code and output from executed process
    :raises:
        :class:`CalledProcessError`
    """
    _LOGGER.debug('invoke: %r', cmd)
    args = _alias_command(cmd)

    # Setup a copy of the environ with the provided overrides
    cmd_environ = dict(os.environ.items())
    cmd_environ.update(**environ)

    # Encode any input from unicode
    if cmd_input is not None:
        cmd_input = cmd_input.encode()

    try:
        proc = subprocess.Popen(args,
                                close_fds=_CLOSE_FDS, shell=False,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                env=cmd_environ)
        (out, _err) = proc.communicate(cmd_input)
        retcode = proc.returncode

    except Exception:
        _LOGGER.exception('Error invoking %r', args)
        raise

    # Decode output back into unicode
    out = out.decode()

    if retcode != 0 and use_except:
        _LOGGER.error('Command failed: rc:%d: %s', retcode, out)
        raise CalledProcessError(cmd=args,
                                 returncode=retcode,
                                 output=out)

    return (retcode, out)


def popen(cmdline, environ=(), stdin=None, stdout=None, stderr=None):
    """Open a subprocess wrapping subprocess.Popen.

    :param cmdline:
        Command to run
    :type cmdline:
        ``list``
    :param environ:
        *optional* Environ variable to set prior to running the command
    :type environ:
        ``dict``
    :param stdin:
        *optional* File object to hook to the subprocess' stdin
    :type stdin:
        ``file object``
    :param stdout:
        *optional* File object to hook to the subprocess' stdout
    :type stdout:
        ``file object``
    :param stderr:
        *optional* File object to hook to the subprocess' stderr
    :type stderr:
        ``file object``
    """
    _LOGGER.debug('popen: %r', cmdline)
    args = _alias_command(cmdline)

    # Setup a copy of the environ with the provided overrides
    cmd_environ = dict(os.environ.items())
    cmd_environ.update(environ)

    return subprocess.Popen(
        args,
        close_fds=_CLOSE_FDS, shell=False,
        stdin=stdin or subprocess.PIPE,
        stdout=stdout or subprocess.PIPE,
        stderr=stderr or subprocess.PIPE,
        env=cmd_environ
    )


def exec_pid1(cmd, ipc=True, mount=True, proc=True,
              close_fds=True, restore_signals=True,
              propagation=None):
    """Exec command line under pid1.
    """
    pid1 = _resolve('pid1')
    safe_cmd = _alias_command(cmd)
    args = [pid1]
    if ipc:
        args.append('-i')
    if mount:
        args.append('-m')
    if proc:
        args.append('-p')
    if propagation is not None:
        args.append('--propagation')
        args.append(propagation)

    args.extend(safe_cmd)
    _LOGGER.debug('exec_pid1: %r', args)
    utils.sane_execvp(args[0], args,
                      close_fds=close_fds,
                      signals=restore_signals)


def exec_fghack(cmd, close_fds=True, restore_signals=True):
    """Anti-backgrounding exec command.
    """
    fghack = _resolve('s6_fghack')
    safe_cmd = _alias_command(cmd)
    args = [fghack] + safe_cmd
    _LOGGER.debug('exec_fghack: %r', args)
    utils.sane_execvp(
        args[0], args,
        close_fds=close_fds,
        signals=restore_signals
    )


def safe_exec(cmd, close_fds=True, restore_signals=True):
    """Exec command line using os.execvp.
    """
    safe_cmd = _alias_command(cmd)
    _LOGGER.debug('safe_exec: %r', safe_cmd)

    utils.sane_execvp(
        safe_cmd[0], safe_cmd,
        close_fds=close_fds,
        signals=restore_signals
    )


__all__ = [
    'call',
    'CalledProcessError',
    'check_call',
    'check_output',
    'exec_pid1',
    'get_aliases',
    'invoke',
    'resolve',
    'safe_exec',
]
