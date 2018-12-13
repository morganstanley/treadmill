"""Supervisor definition anc control.

Linux:

Manages daemontools-like services inside the container.

For each application container there may be multiple services defined, which
are controlled by skarnet.org s6 supervision suite.

Application container is started in chrooted environment, and the root
directory structure::

    /
    /services/
        foo/
        bar/

Application container is started with the supervisor monitoring the services
directory using 'svscan /services'. The svscan become the container 'init' -
parent to all processes inside container.

Treadmill will put svscan inside relevant cgroup hierarchy and subsystems.

Once started, services are added by created subdirectory for each service.

The following files are created in each directory:

 - run
 - app.sh

The run file is executed by s6-supervise. The run file will perform the
following actions:

 - setuidgid - change execution context to the proid
 - softlimit - part of the suite, set process limits
 - setlock ../../<app.name> - this will create a lock monitored by Treadmill,
   so that Treadmill is notified when the app exits.
 - exec app.sh

All services will be started by Treadmill runtime using 's6-svc' utility. Each
service will be started with 'svc -o' (run once) option, and Treadmill will
be responsible for restart and maintaining restart count.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import enum  # pylint: disable=wrong-import-order
import errno
import json
import logging
import os
import time

from treadmill import fs
from treadmill import utils
from treadmill import subproc
from treadmill import templates

from . import _service_base
from . import _utils as supervisor_utils

if os.name == 'nt':
    from . import winss as sup_impl
    _PREFIX = 'winss'
else:
    from . import s6 as sup_impl
    _PREFIX = 's6'


_LOGGER = logging.getLogger(__name__)

# svc exits 111 if it cannot send a command.
ERR_COMMAND = 111

# svc exits 100 if no supervise process is running on servicedir.
ERR_NO_SUP = 100

# svc exits 99 if a timed request timeouts.
ERR_TIMEOUT = 99

EXITS_DIR = 'exits'


class InvalidServiceDirError(ValueError):
    """Invalid service directory.
    """


def open_service(service_dir, existing=True):
    """Open a service object from a service directory.

    :param ``str`` service_dir:
        Location of the service to open.
    :param ``bool`` existing:
        Whether the service must already exist
    :returns ``_service_base.Service``:
        Instance of a service
    """
    if not isinstance(service_dir, _service_base.Service):
        svc_data = _service_base.Service.read_dir(
            service_dir
        )
        if svc_data is None:
            if existing:
                raise InvalidServiceDirError(
                    'Invalid Service directory: %r' % service_dir
                )
            else:
                svc_type = _service_base.ServiceType.LongRun
                svc_basedir = os.path.dirname(service_dir)
                svc_name = os.path.basename(service_dir)

        else:
            svc_type, svc_basedir, svc_name = svc_data

        return sup_impl.create_service(
            svc_basedir=svc_basedir,
            svc_name=svc_name,
            svc_type=svc_type
        )

    return service_dir


# Disable W0613: Unused argument 'kwargs' (for s6/winss compatibility)
# pylint: disable=W0613
def _create_scan_dir_s6(scan_dir, finish_timeout, wait_cgroups=None,
                        kill_svc=None, **kwargs):
    """Create a scan directory.

    :param ``str`` scan_dir:
        Location of the scan directory.
    :param ``int`` finish_timeout:
        The finish script timeout.
    :param ``str`` wait_cgroups:
        Instruct the finish procedure to wait on all processes in the cgroup.
    :param ``str`` kill_svc:
        The service to kill before shutdown.
    :returns ``_service_dir_base.ServiceDirBase``:
        Instance of a service dir
    """
    if not isinstance(scan_dir, sup_impl.ScanDir):
        scan_dir = sup_impl.ScanDir(scan_dir)

    svscan_finish_script = templates.generate_template(
        's6.svscan.finish',
        timeout=finish_timeout,
        wait_cgroups=wait_cgroups,
        _alias=subproc.get_aliases()
    )
    scan_dir.finish = svscan_finish_script
    svscan_sigterm_script = templates.generate_template(
        's6.svscan.sigterm',
        kill_svc=kill_svc,
        _alias=subproc.get_aliases()
    )
    scan_dir.sigterm = svscan_sigterm_script
    svscan_sighup_script = templates.generate_template(
        's6.svscan.sighup',
        kill_svc=kill_svc,
        _alias=subproc.get_aliases()
    )
    scan_dir.sighup = svscan_sighup_script
    svscan_sigint_script = templates.generate_template(
        's6.svscan.sigint',
        kill_svc=kill_svc,
        _alias=subproc.get_aliases()
    )
    scan_dir.sigint = svscan_sigint_script
    svscan_sigquit_script = templates.generate_template(
        's6.svscan.sigquit',
        kill_svc=kill_svc,
        _alias=subproc.get_aliases()
    )
    scan_dir.sigquit = svscan_sigquit_script
    return scan_dir


# Disable W0613: Unused argument 'kwargs' (for s6/winss compatibility)
# pylint: disable=W0613
def _create_scan_dir_winss(scan_dir, finish_timeout, kill_svc=None, **kwargs):
    """Create a scan directory.

    :param ``str`` scan_dir:
        Location of the scan directory.
    :param ``int`` finish_timeout:
        The finish script timeout.
    :param ``str`` kill_svc:
        The service to kill before shutdown.
    :returns ``_service_dir_base.ServiceDirBase``:
        Instance of a service dir
    """
    if not isinstance(scan_dir, sup_impl.ScanDir):
        scan_dir = sup_impl.ScanDir(scan_dir)

    svscan_finish_script = templates.generate_template(
        'winss.svscan.finish',
        timeout=finish_timeout,
        scan_dir=scan_dir.directory,
        _alias=subproc.get_aliases()
    )
    scan_dir.finish = svscan_finish_script
    svscan_sigterm_script = templates.generate_template(
        'winss.svscan.sigterm',
        kill_svc=kill_svc,
        _alias=subproc.get_aliases()
    )
    scan_dir.sigterm = svscan_sigterm_script
    return scan_dir


# Disable C0103: Invalid constant name "create_service"
# pylint: disable=C0103
if _PREFIX == 'winss':
    create_scan_dir = _create_scan_dir_winss
else:
    create_scan_dir = _create_scan_dir_s6


def create_environ_dir(env_dir, env, update=False):
    """Create/update environment directory for the supervisor.
    """
    fs.mkdir_safe(env_dir)

    supervisor_utils.environ_dir_write(
        env_dir, env,
        update=update
    )


def read_environ_dir(env_dir):
    """Read an existing environ directory into a ``dict``.

    :returns:
        ``dict`` - Dictionary of environment variables.
    """
    try:
        return supervisor_utils.environ_dir_read(env_dir)
    except (OSError, IOError) as err:
        if err.errno == errno.ENOENT:
            return {}
        else:
            raise


# Disable W0613: Unused argument 'kwargs' (for s6/winss compatibility)
# pylint: disable=W0613
def _create_service_s6(base_dir,
                       name,
                       app_run_script,
                       userid='root',
                       downed=False,
                       environ_dir=None,
                       environ=None,
                       environment='prod',
                       monitor_policy=None,
                       trace=None,
                       timeout_finish=None,
                       notification_fd=None,
                       call_before_run=None,
                       call_before_finish=None,
                       run_script='s6.run',
                       log_run_script='s6.logger.run',
                       finish_script='s6.finish',
                       logger_args=None,
                       ionice_prio=None,
                       **kwargs):
    """Initializes service directory.

    Creates run, finish scripts as well as log directory with appropriate
    run script.
    """
    # Disable R0912: Too many branches
    # pylint: disable=R0912
    try:
        home_dir = utils.get_userhome(userid)
        shell = utils.get_usershell(userid)

    except KeyError:
        # Check the identity we are going to run as. It needs to exists on the
        # host or we will fail later on as we try to seteuid.
        _LOGGER.exception('Unable to find userid %r in passwd database.',
                          userid)
        raise

    if isinstance(base_dir, sup_impl.ScanDir):
        # We are given a scandir as base, use it.
        svc = base_dir.add_service(name, _service_base.ServiceType.LongRun)
    else:
        svc = LongrunService(base_dir, name)

    # Setup the environ
    if environ is None:
        svc_environ = {}
    else:
        svc_environ = environ.copy()
    svc_environ['HOME'] = home_dir
    svc.environ = svc_environ

    if ionice_prio is None:
        if environment == 'prod':
            ionice_prio = 5
        else:
            ionice_prio = 6

    # Setup the run script
    svc.run_script = templates.generate_template(
        run_script,
        user=userid,
        shell=shell,
        environ_dir=environ_dir,
        trace=trace,
        ionice_prio=ionice_prio,
        call_before_run=call_before_run,
        _alias=subproc.get_aliases()
    )

    if monitor_policy is not None or call_before_finish is not None:
        # Setup the finish script
        svc.finish_script = templates.generate_template(
            finish_script,
            monitor_policy=monitor_policy,
            trace=trace,
            call_before_finish=call_before_finish,
            _alias=subproc.get_aliases()
        )

    if log_run_script is not None:
        if logger_args is None:
            logger_args = '-b -p T n20 s1000000'

        # Setup the log run script
        svc.log_run_script = templates.generate_template(
            log_run_script,
            logdir=os.path.relpath(
                os.path.join(svc.data_dir, 'log'),
                svc.logger_dir
            ),
            logger_args=logger_args,
            _alias=subproc.get_aliases()
        )

    svc.default_down = bool(downed)
    svc.notification_fd = notification_fd

    if monitor_policy is not None:
        svc.timeout_finish = 0
        if monitor_policy['limit'] > 0:
            exits_dir = os.path.join(svc.data_dir, EXITS_DIR)
            fs.mkdir_safe(exits_dir)
            fs.rm_children_safe(exits_dir)
    else:
        svc.timeout_finish = timeout_finish

    svc.write()

    # Write the app_start script
    supervisor_utils.script_write(
        os.path.join(svc.data_dir, 'app_start'),
        app_run_script
    )

    return svc


# Disable W0613: Unused argument 'kwargs' (for s6/winss compatibility)
# pylint: disable=W0613
def _create_service_winss(base_dir,
                          name,
                          app_run_script,
                          downed=False,
                          environ=None,
                          monitor_policy=None,
                          timeout_finish=None,
                          run_script='winss.run',
                          log_run_script='winss.logger.run',
                          finish_script='winss.finish',
                          **kwargs):
    """Initializes service directory.

    Creates run, finish scripts as well as log directory with appropriate
    run script.
    """
    if isinstance(base_dir, sup_impl.ScanDir):
        # We are given a scandir as base, use it.
        svc = base_dir.add_service(name, _service_base.ServiceType.LongRun)
    else:
        svc = LongrunService(base_dir, name)

    # Setup the environ
    if environ is None:
        svc_environ = {}
    else:
        svc_environ = environ.copy()

    svc.environ = svc_environ

    # Setup the run script
    svc.run_script = templates.generate_template(
        run_script,
        app_run_script=app_run_script,
        _alias=subproc.get_aliases()
    )

    if monitor_policy is not None:
        # Setup the finish script
        svc.finish_script = templates.generate_template(
            finish_script,
            monitor_policy=monitor_policy,
            _alias=subproc.get_aliases()
        )

    logdir = os.path.join(svc.data_dir, 'log')
    fs.mkdir_safe(logdir)

    if log_run_script is not None:
        # Setup the log run script
        svc.log_run_script = templates.generate_template(
            log_run_script,
            logdir=os.path.relpath(
                logdir,
                svc.logger_dir
            ),
            _alias=subproc.get_aliases()
        )

    svc.default_down = bool(downed)
    if monitor_policy is not None:
        svc.timeout_finish = 0
        if monitor_policy['limit'] > 0:
            exits_dir = os.path.join(svc.data_dir, EXITS_DIR)
            fs.mkdir_safe(exits_dir)
            fs.rm_children_safe(exits_dir)
    else:
        svc.timeout_finish = timeout_finish

    svc.write()

    return svc


# Disable C0103: Invalid constant name "create_service"
# pylint: disable=C0103
if _PREFIX == 'winss':
    create_service = _create_service_winss
else:
    create_service = _create_service_s6


class ServiceWaitAction(enum.Enum):
    """Enumeration of wait actions."""
    # pylint complains: Invalid class attribute name "up"
    up = 'u'  # pylint: disable=C0103
    down = 'd'
    really_up = 'U'
    really_down = 'D'


class ServiceControlAction(enum.Enum):
    """Enumeration of control actions."""
    kill = 'k'
    once = 'o'
    once_at_most = 'O'
    down = 'd'
    # pylint complains: Invalid class attribute name "up"
    up = 'u'  # pylint: disable=C0103
    exit = 'x'


class SvscanControlAction(enum.Enum):
    """Enumeration of control actions."""
    alarm = 'a'
    abort = 'b'
    nuke = 'n'
    quit = 'q'
    exit = 'x'


def _get_cmd(cmd):
    return _PREFIX + '_' + cmd


def _get_wait_action(action):
    if os.name == 'nt' and action == ServiceWaitAction.really_up:
        action = ServiceWaitAction.up

    return action


def is_supervised(service_dir):
    """Checks if the supervisor is running."""
    try:
        subproc.check_call([_get_cmd('svok'), service_dir])
        return True
    except subproc.CalledProcessError as err:
        # svok returns 1 when the service directory is not supervised.
        if err.returncode == 1:
            return False
        else:
            raise


def control_service(service_dir, actions, wait=None, timeout=0):
    """Sends a control signal to the supervised process.

    :returns:
        ``True`` - Command was successuful.
        ``False`` - Command timedout (only if `wait` was provided).
    :raises ``subproc.CalledProcessError``:
        With `returncode` set to `ERR_NO_SUP` if the service is not supervised.
        With `returncode` set to `ERR_COMMAND` if there is a problem
        communicating with the supervisor.
    """
    cmd = [_get_cmd('svc')]

    if wait:
        cmd.append('-w' + _get_wait_action(wait).value)
        if timeout > 0:
            cmd.extend(['-T{}'.format(timeout)])

    action_str = '-'
    for action in utils.get_iterable(actions):
        action_str += action.value

    cmd.append(action_str)
    cmd.append(service_dir)

    try:
        subproc.check_call(cmd)

    except subproc.CalledProcessError as err:
        if err.returncode == ERR_TIMEOUT:
            return False
        else:
            raise

    return True


def control_svscan(scan_dir, actions):
    """Sends a control signal to a svscan instance."""
    action_str = '-'
    for action in utils.get_iterable(actions):
        action_str += action.value

    subproc.check_call([_get_cmd('svscanctl'), action_str, scan_dir])


def wait_service(service_dirs, action, all_services=True, timeout=0):
    """Performs a wait task on the given list of service directories.
    """
    cmd = [_get_cmd('svwait')]

    if timeout > 0:
        cmd.extend(['-t{}'.format(timeout)])

    if not all_services:
        cmd.append('-o')

    cmd.append('-' + _get_wait_action(action).value)
    cmd.extend(utils.get_iterable(service_dirs))

    subproc.check_call(cmd)


def ensure_not_supervised(service_dir):
    """Waits for the service and log service to not be supervised."""
    service_dirs = []
    if is_supervised(service_dir):
        service_dirs.append(service_dir)

    log_dir = os.path.join(service_dir, 'log')
    if os.path.exists(log_dir) and is_supervised(log_dir):
        service_dirs.append(log_dir)

    for service in service_dirs:
        try:
            # Close supervised process as it should have already
            # been told to go down
            _LOGGER.info('Force service %s to exit', service)
            control_service(service, ServiceControlAction.exit,
                            ServiceWaitAction.really_down,
                            timeout=1000)
        except subproc.CalledProcessError:
            # Ignore this as supervisor may be down
            pass

        count = 0
        while is_supervised(service):
            count += 1
            if count == 600:
                raise Exception(
                    'Service dir {0} failed to stop in 60s.'.format(service)
                )
            time.sleep(0.1)


ScanDir = sup_impl.ScanDir
LongrunService = sup_impl.LongrunService
ServiceType = _service_base.ServiceType

__all__ = [
    'ERR_COMMAND',
    'ERR_NO_SUP',
    'EXITS_DIR',
    'LongrunService',
    'ScanDir',
    'ServiceControlAction',
    'ServiceType',
    'ServiceWaitAction',
    'SvscanControlAction',
    'control_service',
    'control_svscan',
    'create_environ_dir',
    'create_scan_dir',
    'create_service',
    'is_supervised',
    'open_service',
    'read_environ_dir',
    'wait_service',
]

if _PREFIX == 's6':
    BundleService = sup_impl.BundleService
    OneshotService = sup_impl.OneshotService

    __all__ += [
        'BundleService',
        'OneshotService',
    ]
