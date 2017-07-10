"""Manages daemontools-like services inside the container.

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

import json
import logging
import os
import subprocess

if os.name == 'posix':
    import pwd

import enum
import jinja2

from treadmill import fs
from treadmill import s6
from treadmill import subproc
from treadmill import utils

_LOGGER = logging.getLogger(__name__)

JINJA2_ENV = jinja2.Environment(loader=jinja2.PackageLoader(__name__))

# s6-svc exits 111 if it cannot send a command.
ERR_COMMAND = 111

# s6-svc exits 100 if no s6-supervise process is running on servicedir.
ERR_NO_SUP = 100

POLICY_JSON = 'policy.json'
TRACE_FILE = 'trace'


def open_service(service_dir, existing=True):
    """Open a service object from a service directry.

    :param ``str`` service_dir:
        Location of the service to open.
    :param ``bool`` existing:
        Whether the service must already exist
    :returns ``s6.Service``:
        Instance of a service
    """
    if not isinstance(service_dir, s6.Service):
        service = s6.Service.from_dir(service_dir)
        if service is None:
            if existing:
                raise ValueError('Invalid Service directory: %r' % service_dir)
            else:
                service = s6.Service.new(
                    svc_basedir=os.path.dirname(service_dir),
                    svc_name=os.path.basename(service_dir),
                    svc_type=s6.ServiceType.LongRun
                )
        return service

    return service_dir


def create_services_dir(services_dir,
                        finish_timeout):
    """Create a service directory.
    """

    if not isinstance(services_dir, s6.ServiceDir):
        services_dir = s6.ServiceDir.from_dir(services_dir)

    svcdir_finish_script = utils.generate_template(
        's6.svscan.finish',
        timeout=finish_timeout,
        services_dir=services_dir.directory,
        _alias=subproc.get_aliases()
    )
    services_dir.finish = svcdir_finish_script
    return services_dir


def create_service(services_dir,
                   name,
                   userid,
                   app_run_script,
                   downed=False,
                   environ_dir=None,
                   environ=None,
                   environment='prod',
                   monitor_policy=None,
                   trace=None,
                   run_script='s6.run',
                   log_run_script='s6.logger.run',
                   finish_script='s6.finish'):
    """Initializes service directory.

    Creates run, finish scripts as well as log directory with appropriate
    run script.
    """
    try:
        user_pw = pwd.getpwnam(userid)

    except KeyError:
        # Check the identity we are going to run as. It needs to exists on the
        # host or we will fail later on as we try to seteuid.
        _LOGGER.exception('Unable to find userid %r in passwd database.',
                          userid)
        raise

    if not isinstance(services_dir, s6.ServiceDir):
        services_dir = s6.ServiceDir.from_dir(services_dir)

    svc = services_dir.add_service(name, s6.ServiceType.LongRun)
    # Setup the environ
    if environ is None:
        svc_environ = {}
    else:
        svc_environ = environ.copy()
    svc_environ['HOME'] = user_pw.pw_dir
    svc.environ = svc_environ

    if environment == 'prod':
        ionice_prio = 5
    else:
        ionice_prio = 6

    # Setup the run script
    svc.run_script = utils.generate_template(
        run_script,
        user=userid,
        shell=user_pw.pw_shell,
        environ_dir=environ_dir,
        monitored=(monitor_policy is not None),
        ionice_prio=ionice_prio,
        _alias=subproc.get_aliases()
    )
    # Setup the finish script
    svc.finish_script = utils.generate_template(
        finish_script,
        _alias=subproc.get_aliases()
    )
    # Setup the log run script
    svc.log_run_script = utils.generate_template(
        log_run_script,
        logdir=os.path.relpath(
            os.path.join(svc.data_dir, 'log'),
            svc.logger_dir
        ),
        _alias=subproc.get_aliases()
    )
    svc.default_down = bool(downed)
    svc.write()

    # Write the app_start script
    s6.script_write(
        os.path.join(svc.data_dir, 'app_start'),
        app_run_script
    )
    # Optionally write a monitor policy file
    if monitor_policy is not None:
        s6.data_write(
            os.path.join(svc.data_dir, POLICY_JSON),
            json.dumps(monitor_policy)
        )
    # Optionally write trace information file
    if trace is not None:
        s6.data_write(
            os.path.join(svc.data_dir, TRACE_FILE),
            json.dumps(trace)
        )

    return svc


def create_environ_dir(env_dir, env, update=False):
    """Create/update environment directory for s6-envdir.
    """
    fs.mkdir_safe(env_dir)

    s6.environ_dir_write(
        env_dir, env,
        update=update
    )


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


def is_supervised(service_dir):
    """Checks if the supervisor is running."""
    try:
        subproc.check_call(['s6_svok', service_dir])
        return True
    except subprocess.CalledProcessError as err:
        # svok returns 1 when the service directory is not supervised.
        if err.returncode == 1:
            return False
        else:
            raise


def control_service(service_dir, actions, wait=None, timeout=0):
    """Sends a control signal to the supervised process."""
    cmd = ['s6_svc']

    if wait:
        cmd.append('-w' + wait.value)
        if timeout > 0:
            cmd.extend(['-T', str(timeout)])

    action_str = '-'
    for action in utils.get_iterable(actions):
        action_str += action.value

    cmd.append(action_str)
    cmd.append(service_dir)

    try:
        subproc.check_call(cmd)
        return True
    except subprocess.CalledProcessError as err:
        # svc returns 1 on timeout.
        if err.returncode == 1:
            return False
        else:
            raise


def control_svscan(scan_dir, actions):
    """Sends a control signal to a svscan instance."""
    action_str = '-'
    for action in utils.get_iterable(actions):
        action_str += action.value

    subproc.check_call(['s6_svscanctl', action_str, scan_dir])


def wait_service(service_dirs, action, all_services=True, timeout=0):
    """Performs a wait task on the given list of service directories."""
    cmd = ['s6_svwait']

    if timeout > 0:
        cmd.extend(['-t', str(timeout)])

    if not all_services:
        cmd.append('-o')

    cmd.append('-' + action.value)
    cmd.extend(utils.get_iterable(service_dirs))

    try:
        subproc.check_call(cmd)
        return True
    except subprocess.CalledProcessError as err:
        # svwait returns 99 on timeout.
        if err.returncode == 99:
            return False
        else:
            raise
