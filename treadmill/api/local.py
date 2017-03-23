"""Implementation of allocation API."""


import glob
import errno
import logging
import os
import tarfile

import yaml

from .. import appmgr


_LOGGER = logging.getLogger(__name__)


class API(object):
    """Treadmill Local REST api."""

    def __init__(self):

        self._app_env = None

        def app_env():
            """Lazy instantiate app environment."""
            if not self._app_env:
                # TODO: we need to pass this parameter to api, unfortunately
                #       in current api framework it is not trivial.
                approot = os.environ['TREADMILL_APPROOT']
                _LOGGER.info('Using approot: %s', approot)
                self._app_env = appmgr.AppEnvironment(approot)

            return self._app_env

        def _archive_path(archive_type, instance, uniq):
            """Return archive path given archive id and type."""
            return os.path.join(
                app_env().archives_dir,
                '%s-%s.%s.tar.gz' % (instance.replace('#', '-'),
                                     uniq,
                                     archive_type)
            )

        def _app_path(instance, uniq):
            """Return archive path given archive id and type."""
            return os.path.join(
                app_env().apps_dir,
                '%s-%s' % (instance.replace('#', '-'), uniq)
            )

        def _list_running():
            """List all running instances."""
            result = {}
            running_glob = os.path.join(app_env().running_dir, '*')
            for running in glob.glob(running_glob):
                try:
                    app_path = os.readlink(running)
                    full_name = os.path.basename(app_path)
                    name, instance, uniq = full_name.rsplit('-', 2)
                    ctime = os.stat(app_path).st_ctime
                    result[full_name] = {
                        '_id': '%s#%s/%s' % (name, instance, uniq),
                        'ctime': ctime,
                        'state': 'running',
                    }
                except OSError as oserr:
                    if oserr.errno == errno.ENOENT:
                        continue

            return result

        def _list_finished():
            """List all finished instances."""
            result = {}
            archive_glob = os.path.join(app_env().archives_dir, '*.sys.tar.gz')
            for archive in glob.glob(archive_glob):
                try:
                    full_name = os.path.basename(archive)[:-len('.sys.tar.gz')]
                    name, instance, uniq = full_name.rsplit('-', 2)
                    ctime = os.stat(archive).st_ctime
                    result[full_name] = {
                        '_id': '%s#%s/%s' % (name, instance, uniq),
                        'ctime': ctime,
                        'state': 'finished',
                    }
                except OSError as oserr:
                    if oserr.errno == errno.ENOENT:
                        continue
            return result

        def _list(state=None):
            """List all instances on the node."""
            result = {}
            if state is None or state == 'running':
                result.update(_list_running())
            if state is None or state == 'finished':
                result.update(_list_finished())
            return result.values()

        # TODO: implementation of this is placeholder, need to think about
        #       more relevant info.
        def _get(uniqid):
            """Get instance info."""
            instance, uniq = uniqid.split('/')
            if uniq == 'running':
                fname = os.path.join(app_env().running_dir, instance,
                                     'state.yml')
            else:
                fname = os.path.join(_app_path(instance, uniq), 'state.yml')

            try:
                with open(fname) as f:
                    return yaml.load(f.read())
            except EnvironmentError as err:
                if uniq == 'running' or err.errno != errno.ENOENT:
                    raise

                fname = _archive_path('sys', instance, uniq)
                with tarfile.open(fname) as archive:
                    member = archive.extractfile('state.yml')
                    return yaml.load(member.read())

        def _yield_log(instance, uniq, logtype, component):
            """Yield lines from the log file."""
            _LOGGER.info('Log: %s %s %s %s',
                         instance, uniq, logtype, component)
            if logtype == 'sys':
                logfile = os.path.join('sys', component, 'log', 'current')
            else:
                logfile = os.path.join('services', component, 'log', 'current')

            if uniq == 'running':
                fname = os.path.join(app_env().running_dir, instance, logfile)
            else:
                fname = os.path.join(_app_path(instance, uniq), logfile)

            try:
                with open(fname) as f:
                    for line in f:
                        yield line

            except EnvironmentError as err:
                if uniq == 'running' or err.errno != errno.ENOENT:
                    raise

                fname = _archive_path(logtype, instance, uniq)
                _LOGGER.info('From archive: %s', fname)

                with tarfile.open(fname) as archive:
                    member = archive.extractfile(logfile)
                    for line in member:
                        yield line

        class _LogAPI(object):
            """Access to log files."""
            def __init__(self):

                def _get(log_id):
                    """Get log file."""
                    instance, uniq, logtype, component = log_id.split('/')
                    return _yield_log(instance, uniq, logtype, component)

                self.get = _get

        class _ArchiveAPI(object):
            """Access to archive files."""
            def __init__(self):

                def _get(archive_id):
                    """Get log file."""
                    instance, uniq, logtype = archive_id.split('/')
                    return _archive_path(logtype, instance, uniq)

                self.get = _get

        self.list = _list
        self.get = _get
        self.log = _LogAPI()
        self.archive = _ArchiveAPI()


def init(_authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return api
