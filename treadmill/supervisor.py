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


import glob
import logging
import os
import stat
import subprocess
import time

import jinja2

from . import fs
from . import utils
from . import subproc


_LOGGER = logging.getLogger(__name__)

EXEC_MODE = (stat.S_IRUSR |
             stat.S_IRGRP |
             stat.S_IROTH |
             stat.S_IWUSR |
             stat.S_IXUSR |
             stat.S_IXGRP |
             stat.S_IXOTH)

JINJA2_ENV = jinja2.Environment(loader=jinja2.PackageLoader(__name__))

# s6-svc exits 111 if it cannot send a command.
ERR_COMMAND = 111

# s6-svc exits 100 if no s6-supervise process is running on servicedir.
ERR_NO_SUP = 100


def create_service(app_root, user, home, shell, service, runcmd,
                   env=None, down=True, envdirs=None, as_root=True,
                   template=None):
    """Initializes service directory.

    Creates run, finish scripts as well as log directory with appropriate
    run script.
    """
    real_svc_dir = os.path.join(app_root, service)
    fs.mkdir_safe(real_svc_dir)

    with open(os.path.join(real_svc_dir, 'app_start'), 'w') as f:
        f.write(runcmd)

    if template is None:
        template = 'supervisor.run'

    cmd = '/services/{0}/app_start'.format(service)

    if envdirs is None:
        envdirs = []

    utils.create_script(os.path.join(real_svc_dir, 'run'),
                        template,
                        service=service,
                        user=user,
                        home=home,
                        shell=shell,
                        cmd=cmd,
                        env=env,
                        envdirs=envdirs,
                        as_root=as_root)

    utils.create_script(os.path.join(real_svc_dir, 'finish'),
                        'supervisor.finish',
                        service=service, user=user, cmds=[])

    if down:
        with open(os.path.join(real_svc_dir, 'down'), 'w'):
            pass


def exec_root_supervisor(directory):
    """Execs svscan in the directory."""
    if os.name == 'nt':
        subproc.call(['s6-svscan', directory])
    else:
        subproc.exec_pid1(['s6-svscan', directory])


def start_service(app_root, service, once=True):
    """Starts a service in the app_root/services/service directory."""
    if once:
        opt = '-o'
    else:
        opt = '-u'
    subprocess.call(['s6-svc', opt, os.path.join(app_root, service)])


def stop_service(app_root, service):
    """Stops the service and do not restart it."""
    subprocess.call(['s6-svc', '-d', os.path.join(app_root, service)])


def kill_service(app_root, service, signal='TERM'):
    """Send the service the specified signal."""
    signal_opts = dict([
        ('STOP', '-p'),
        ('CONT', '-c'),
        ('HUP', '-h'),
        ('ALRM', '-a'),
        ('INT', '-i'),
        ('TERM', '-t'),
        ('KILL', '-k')
    ])

    if signal not in signal_opts:
        utils.fatal('Unsupported signal: %s', signal)
    opt = signal_opts[signal]
    subprocess.call(['s6-svc', opt, os.path.join(app_root, service)])


def is_supervisor_running(app_root, service):
    """Checks if the supervisor is running."""
    # svok returns 0 if supervisor is running.
    try:
        subproc.check_call(['s6-svok', os.path.join(app_root, service)],
                           stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError as err:
        _LOGGER.info('exit code: %d, %s', err.returncode, err.cmd)
        if err.output:
            _LOGGER.info(err.output)
        return False


def is_running(app_root, service):
    """Checks if the service is running."""
    return bool(get_pid(app_root, service))


def get_pid(app_root, service):
    """Returns pid of the service or None if the service is not running."""
    output = subproc.check_output(['s6-svstat',
                                   os.path.join(app_root, service)])
    return _parse_state(output).get('pid', None)


def _parse_state(state):
    """Parses svstat output into dict.

    The dict will have the following attributes:
     - state - 'up'/'down'
     - intended - original state of the service when it was created.
     - since - time when state transition changed.
     - pid - pid of the process or None if state is down.
    """
    # The structure of the output is:
    #
    # up (pid $pid) $sec seconds
    # up (pid $pid) $sec seconds, normally down
    # down $sec seconds
    # down $sec seconds, normally down
    state = state.strip()
    tokens = state.split(' ')
    actual = tokens[0]
    intended = actual
    pid = None
    since = int(time.time())
    if actual == 'up':
        # remove extra )
        pid = int(tokens[2][:-1])
        # TODO: check if it can output time in hours (hope not).
        since = since - int(tokens[3])
        if tokens[-1] == 'down':
            intended = 'down'
    elif actual == 'down':
        since = since - int(tokens[1])
        if tokens[-1] == 'up':
            intended = 'up'

    return {'pid': pid, 'since': since, 'state': actual, 'intended': intended}


def get_state(svcroot):
    """Checks the state of services under given root."""
    services = glob.glob(os.path.join(svcroot, '*'))
    services_state = {}
    for service in services:
        state = subproc.check_output(['s6-svstat', service])
        services_state[os.path.basename(service)] = _parse_state(state)

    return services_state


def _service_wait(svcroot, up_opt, any_all_opt, timeout=0, subset=None):
    """Given services directory, wait for services to be in given state."""
    services = glob.glob(os.path.join(svcroot, '*'))
    if subset is not None:
        services = [svc for svc in services if os.path.basename(svc) in subset]

    if not services:
        return

    cmdline = ['s6-svwait', up_opt, '-t', str(timeout), any_all_opt] + services

    # This will block until service status changes or timeout expires.
    subproc.check_call(cmdline)


def wait_all_up(svcroot, timeout=0, subset=None):
    """Waits for services to be up."""
    _service_wait(svcroot, up_opt='-u', any_all_opt='-a', timeout=timeout,
                  subset=subset)


def wait_all_down(svcroot, timeout=0, subset=None):
    """Waits for services to be up."""
    _service_wait(svcroot, up_opt='-d', any_all_opt='-a', timeout=timeout,
                  subset=subset)


def wait_any_up(svcroot, timeout=0, subset=None):
    """Waits for services to be up."""
    _service_wait(svcroot, up_opt='-u', any_all_opt='-o', timeout=timeout,
                  subset=subset)


def wait_any_down(svcroot, timeout=0, subset=None):
    """Waits for services to be up."""
    _service_wait(svcroot, up_opt='-d', any_all_opt='-o', timeout=timeout,
                  subset=subset)


def create_environ_dir(env_dir, env):
    """Create environment directory for s6-envdir."""
    fs.mkdir_safe(env_dir)

    for key, value in env.items():
        with open(os.path.join(env_dir, key), 'w+') as f:
            if value is not None:
                f.write(str(value))
