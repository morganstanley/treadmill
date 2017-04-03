"""Implementation of allocation API."""
from __future__ import absolute_import

import glob
import errno
import logging
import os
import tarfile
import thread

import yaml

from treadmill import appmgr
from treadmill import logcontext as lc
from treadmill import rrdutils
from treadmill.exc import FileNotFoundError


_LOGGER = lc.ContainerAdapter(logging.getLogger(__name__))


def _temp_file_name():
    """Construct a temporary file name for each thread."""
    f_name = 'local-{}.temp'.format(thread.get_ident())

    return os.path.join(os.path.sep, 'tmp', f_name)


def _get_file(fname=None,
              arch_fname=None,
              arch_extract=True,
              arch_extract_fname=None):
    """Return the file pointed by "fname" or extract it from archive.

    Return fname if the specified file exists or extract
    'arch_extract_fname' from 'arch_fname' first and return the path to
    the extracted file.
    """
    if os.path.exists(fname):
        return fname

    if not arch_extract:
        raise FileNotFoundError('{} cannot be found.'.format(fname))

    _LOGGER.info('Extract %s from archive %s', arch_extract_fname, arch_fname)

    if not os.path.exists(arch_fname):
        raise FileNotFoundError('{} cannot be found.'.format(arch_fname))

    try:
        # extract the req. file from the archive and copy it to a temp file
        copy = _temp_file_name()
        with tarfile.open(arch_fname) as archive, open(copy, 'w+b') as copy_fd:
            member = archive.extractfile(arch_extract_fname)
            copy_fd.writelines(member.readlines())
            copy_fd.close()
    except KeyError as err:
        _LOGGER.error(err)
        raise FileNotFoundError('The file {} cannot be found in {}'.format(
            arch_extract_fname, arch_fname))

    return copy


class _MetricsAPI(object):
    """Acess to the locally gathered metrics."""

    def __init__(self, app_env_func):

        self.app_env = app_env_func

    def _remove_ext(self, fname, extension='.rrd'):
        """Returns the basename of a file and removes the extension as well.
        """
        res = os.path.basename(fname)
        res = res[:-len(extension)]

        return res

    def get(self, rsrc_id, as_json=False):
        """Return the rrd metrics."""
        with lc.LogContext(_LOGGER, rsrc_id) as log:
            log.info('Get metrics')
            id_ = self._unpack_id(rsrc_id)
            file_ = self._get_rrd_file(**id_)

            if as_json:
                return rrdutils.get_json_metrics(file_)

            return file_

    def _unpack_id(self, rsrc_id):
        """Decompose resource_id to a dictionary.

        Unpack the (core) service name or the application name and "uniq name"
        from rsrc_id to a dictionary.
        """
        if '/' in rsrc_id:
            app, uniq = rsrc_id.split('/')
            return {'app': app, 'uniq': uniq}

        return {'service': rsrc_id}

    def _get_rrd_file(
            self, service=None,
            app=None, uniq=None,
            arch_extract=True):
        """Return the rrd file path of an app or a core service."""
        if uniq is None:
            return self._core_rrd_file(service)

        if uniq == 'running':
            arch_extract = False
            # find out uniq ...
            state_yml = os.path.join(self.app_env().running_dir, app,
                                     'state.yml')
            with open(state_yml) as f:
                uniq = yaml.load(f.read())['uniqueid']

        return self._app_rrd_file(app, uniq, arch_extract)

    def _app_rrd_file(self, app, uniq, arch_extract=True):
        """Return an application's rrd file."""
        _LOGGER.info('Return %s', self._metrics_fpath(app=app, uniq=uniq))

        return _get_file(
            self._metrics_fpath(app=app, uniq=uniq),
            arch_extract=arch_extract,
            arch_fname=os.path.join(self.app_env().archives_dir,
                                    '%s-%s.sys.tar.gz' %
                                    (app.replace('#', '-'), uniq)),
            arch_extract_fname='metrics.rrd')

    def _core_rrd_file(self, service):
        """Return the given service's rrd file."""
        _LOGGER.info('Return %s', self._metrics_fpath(service))

        return _get_file(self._metrics_fpath(service), arch_extract=False)

    def _metrics_fpath(self, service=None, app=None, uniq=None):
        """Return the rrd metrics file's full path."""
        if service is not None:
            return os.path.join(self.app_env().metrics_dir, 'core',
                                service + '.rrd')

        return os.path.join(self.app_env().metrics_dir, 'apps',
                            '%s-%s.rrd' % (app.replace('#', '-'), uniq))

    def file_path(self, rsrc_id):
        """Return the rrd metrics file path."""
        id_ = self._unpack_id(rsrc_id)

        return self._metrics_fpath(**id_)


class API(object):
    """Treadmill Local REST api."""

    def __init__(self):

        self._app_env = None

        def app_env(_metrics_api=None):
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

        def _list_services():
            """List the local services."""
            result = {}
            services_glob = os.path.join(app_env().init_dir, '*')
            for svc in glob.glob(services_glob):
                try:
                    svc_name = os.path.basename(svc)
                    ctime = os.stat(os.path.join(svc, 'log',
                                                 'current')).st_ctime
                    result[svc] = {
                        '_id': svc_name,
                        'ctime': ctime,
                        'state': 'running',
                        }
                except OSError as oserr:
                    if oserr.errno == errno.ENOENT:
                        continue
            return result

        def _list(state=None, inc_svc=False):
            """List all instances on the node."""
            result = {}
            if state is None or state == 'running':
                result.update(_list_running())
                if inc_svc:
                    result.update(_list_services())
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

        def _get_logfile(instance, uniq, logtype, component):
            """Return the corresponding log file."""
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

            _LOGGER.info('Logfile: %s', fname)
            return _get_file(fname,
                             arch_fname=_archive_path(logtype, instance, uniq),
                             arch_extract=bool(uniq != 'running'),
                             arch_extract_fname=logfile)

        class _LogAPI(object):
            """Access to log files."""
            def __init__(self):

                def _yield_log(log_file):
                    """Generator that returns the content of the log file."""
                    with open(log_file) as log:
                        for line in log:
                            yield line

                def _get(log_id):
                    """Get log file."""
                    instance, uniq, logtype, component = log_id.split('/')
                    return _yield_log(_get_logfile(instance, uniq, logtype,
                                                   component))

                self.get = _get

        class _ArchiveAPI(object):
            """Access to archive files."""
            def __init__(self):

                def _get(archive_id):
                    """Get log file."""
                    instance, uniq, logtype = archive_id.split('/')
                    arch_path = _archive_path(logtype, instance, uniq)
                    if not os.path.exists(arch_path):
                        raise FileNotFoundError(
                            '{} cannot be found.'.format(arch_path))

                    return arch_path

                self.get = _get

        self.list = _list
        self.get = _get
        self.log = _LogAPI()
        self.archive = _ArchiveAPI()
        self.metrics = _MetricsAPI(app_env)


def init(_authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return api
