"""Implementation of local API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import errno
import glob
import io
import json
import logging
import os
import re
import tarfile

import six
from six.moves import _thread

from treadmill import exc
from treadmill import appenv
from treadmill import logcontext as lc
from treadmill import rrdutils

_LOGGER = lc.ContainerAdapter(logging.getLogger(__name__))


def _app_path(tm_env, instance, uniq):
    """Return application path given app env, app id and uniq."""
    return os.path.join(tm_env.apps_dir,
                        '%s-%s' % (instance.replace('#', '-'), uniq))


def _archive_path(tm_env, archive_type, instance, uniq):
    """Return archive path given app env, archive id and type."""
    return os.path.join(tm_env.archives_dir, '%s-%s.%s.tar.gz' %
                        (instance.replace('#', '-'), uniq, archive_type))


def _temp_file_name():
    """Construct a temporary file name for each thread."""
    f_name = 'local-{}.temp'.format(_thread.get_ident())

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
        raise exc.LocalFileNotFoundError(
            '{} cannot be found.'.format(fname)
        )

    _LOGGER.info('Extract %s from archive %s', arch_extract_fname, arch_fname)

    if not os.path.exists(arch_fname):
        raise exc.LocalFileNotFoundError(
            '{} cannot be found.'.format(arch_fname)
        )

    try:
        # extract the req. file from the archive and copy it to a temp file
        copy = _temp_file_name()
        with tarfile.open(arch_fname) as arch, io.open(copy, 'wb') as copy_fd:
            member = arch.extractfile(arch_extract_fname)
            copy_fd.writelines(member.readlines())
            copy_fd.close()
    except KeyError as err:
        _LOGGER.error(err)
        raise exc.LocalFileNotFoundError(
            'The file {} cannot be found in {}'.format(arch_extract_fname,
                                                       arch_fname))

    return copy


def _fragment(iterable, start=0, limit=None):
    """
    Selects a fragment of the iterable and returns the items in 'normal order'.

    The lowest index is 0 and designates the first line of the file.
    'Limit' specifies the number of lines to return.
    """
    # TODO: Naive implementation. Needs to be rewritten to a solution with
    # file pointer moving around etc. if it turns out that this isn't
    # performant enough.
    if limit >= 0:
        try:
            fragment = collections.deque(maxlen=limit)
            steps_to_make = start + limit
            while steps_to_make:
                fragment.append(six.next(iterable))
                steps_to_make = steps_to_make - 1
        except StopIteration:
            pass

        try:
            for _ in six.moves.range(min(steps_to_make, start)):
                fragment.popleft()
        except IndexError:
            raise exc.InvalidInputError(
                __name__,
                'Index start=%s is out of range.' % str(start))

        return fragment

    try:
        for _ in six.moves.range(start):
            six.next(iterable)
    except StopIteration:
        raise exc.InvalidInputError(__name__,
                                    'Index start=%s is out of range.'
                                    % str(start))

    return list(iterable)


def _fragment_in_reverse(iterable, start=0, limit=None):
    """
    Selects a fragment of the iterable and returns the items in reverse order.

    The lowest index is 0 and designates the last line of the file.
    'Limit' specifies the number of lines to return.
    """
    # TODO: Naive implementation. Needs to be rewritten to a solution with
    # file pointer moving around etc. if it turns out that this isn't
    # performant enough.
    maxlen = None
    if limit >= 0:
        maxlen = start + limit

    fragment = collections.deque(iterable, maxlen)
    try:
        for _ in six.moves.range(start):
            fragment.pop()
    except IndexError:
        raise exc.InvalidInputError(__name__,
                                    'Index start=%s is out of range.'
                                    % str(start))

    fragment.reverse()
    return fragment


def mk_metrics_api(tm_env):
    """Factory to create metrics api."""

    class _MetricsAPI(object):
        """Acess to the locally gathered metrics."""

        def __init__(self):

            def _get(rsrc_id, timeframe, as_json=False):
                """Return the rrd metrics."""
                with lc.LogContext(_LOGGER, rsrc_id):
                    _LOGGER.info('Get metrics')
                    id_ = self._unpack_id(rsrc_id)
                    file_ = self._get_rrd_file(**id_)

                    if as_json:
                        return rrdutils.get_json_metrics(file_, timeframe)

                    return file_

            def _file_path(rsrc_id):
                """Return the rrd metrics file path."""
                id_ = self._unpack_id(rsrc_id)

                return self._metrics_fpath(**id_)

            self.file_path = _file_path
            self.get = _get

        def _remove_ext(self, fname, extension='.rrd'):
            """Returns the basename of a file and removes the extension as well.
            """
            res = os.path.basename(fname)
            res = res[:-len(extension)]

            return res

        def _unpack_id(self, rsrc_id):
            """Decompose resource_id to a dictionary.

            Unpack the (core) service or the application name and "uniq name"
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
                state_json = os.path.join(tm_env().running_dir, app, 'data',
                                          'state.json')
                with io.open(state_json) as f:
                    uniq = json.load(f)['uniqueid']

            return self._app_rrd_file(app, uniq, arch_extract)

        def _app_rrd_file(self, app, uniq, arch_extract=True):
            """Return an application's rrd file."""
            _LOGGER.info('Return %s', self._metrics_fpath(app=app, uniq=uniq))

            return _get_file(
                self._metrics_fpath(app=app, uniq=uniq),
                arch_extract=arch_extract,
                arch_fname=_archive_path(tm_env(), 'sys', app, uniq),
                arch_extract_fname='metrics.rrd')

        def _core_rrd_file(self, service):
            """Return the given service's rrd file."""
            _LOGGER.info('Return %s', self._metrics_fpath(service))

            return _get_file(self._metrics_fpath(service), arch_extract=False)

        def _metrics_fpath(self, service=None, app=None, uniq=None):
            """Return the rrd metrics file's full path."""
            if service is not None:
                return os.path.join(tm_env().metrics_dir, 'core',
                                    service + '.rrd')

            return os.path.join(tm_env().metrics_dir, 'apps',
                                '%s-%s.rrd' % (app.replace('#', '-'), uniq))

    return _MetricsAPI


def mk_logapi(tm_env):
    """Factory  for log api."""

    class _LogAPI(object):
        """Access to log files."""

        def __init__(self):

            def _get(log_id, start=0, limit=None, order=None):
                """Get log file."""
                instance, uniq, logtype, component = log_id.split('/')
                with lc.LogContext(_LOGGER, '{}/{}'.format(instance, uniq)):
                    log_f = self._get_logfile(instance, uniq,
                                              logtype, component)

                    _LOGGER.info('Requested {} items starting from line {} '
                                 'in {} order'.format(limit, start, order))

                    if start is not None and start < 0:
                        raise exc.InvalidInputError(
                            __name__,
                            'Index cannot be less than 0, got: {}'.format(
                                start
                            )
                        )

                    with io.open(log_f) as log:
                        if order == 'desc':
                            return _fragment_in_reverse(log, start, limit)

                        return _fragment(log, start, limit)

            self.get = _get

        def _get_logfile(self, instance, uniq, logtype, component):
            """Return the corresponding log file."""
            _LOGGER.info('Log: %s %s %s %s',
                         instance, uniq, logtype, component)
            try:
                return self._get_logfile_new(instance, uniq, logtype,
                                             component)
            except exc.LocalFileNotFoundError:
                return self._get_logfile_old(instance, uniq, logtype,
                                             component)

        def _get_logfile_new(self, instance, uniq, logtype, component):
            """Return the log file according to the newer file layout."""

            if logtype == 'sys':
                logfile = os.path.join('sys', component, 'data',
                                       'log', 'current')
            else:
                logfile = os.path.join('services', component, 'data',
                                       'log', 'current')

            if uniq == 'running':
                fname = os.path.join(tm_env().running_dir, instance, 'data',
                                     logfile)
            else:
                fname = os.path.join(
                    _app_path(tm_env(), instance, uniq), 'data', logfile)

            _LOGGER.info('Logfile: %s', fname)

            return _get_file(fname,
                             arch_fname=_archive_path(tm_env(), logtype,
                                                      instance, uniq),
                             arch_extract=bool(uniq != 'running'),
                             arch_extract_fname=logfile)

        def _get_logfile_old(self, instance, uniq, logtype, component):
            """Return the log file according to the old file layout."""
            # TODO: method should be deleted once the old containers disappear

            if logtype == 'sys':
                logfile = os.path.join('sys', component, 'log', 'current')
            else:
                logfile = os.path.join('services', component, 'log', 'current')

            if uniq == 'running':
                fname = os.path.join(tm_env().running_dir, instance, logfile)
            else:
                fname = os.path.join(
                    _app_path(tm_env(), instance, uniq), logfile)

            _LOGGER.info('Logfile: %s', fname)

            return _get_file(fname,
                             arch_fname=_archive_path(tm_env(), logtype,
                                                      instance, uniq),
                             arch_extract=bool(uniq != 'running'),
                             arch_extract_fname=logfile)

    return _LogAPI


class API(object):
    """Treadmill Local REST api."""

    def __init__(self):

        self._tm_env = None

        def tm_env(_metrics_api=None):
            """Lazy instantiate app environment."""
            if not self._tm_env:
                # TODO: we need to pass this parameter to api, unfortunately
                #       in current api framework it is not trivial.
                approot = os.environ['TREADMILL_APPROOT']
                _LOGGER.info('Using approot: %s', approot)
                self._tm_env = appenv.AppEnvironment(approot)

            return self._tm_env

        def _list_running():
            """List all running instances."""
            result = {}
            running_glob = os.path.join(tm_env().running_dir, '*')
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
            archive_glob = os.path.join(tm_env().archives_dir, '*.sys.tar.gz')
            pattern = re.compile(r'''.*/        # archives dir
                                     \w+        # proid
                                     \.         # .
                                     \w+        # app
                                     -\d+       # id
                                     -\w+       # uniq
                                     .sys.tar.gz''', re.X)

            for archive in [f for f in glob.glob(archive_glob)
                            if pattern.match(f)]:
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
            services_glob = os.path.join(tm_env().init_dir, '*')
            for svc in glob.glob(services_glob):
                try:
                    svc_name = os.path.basename(svc)
                    ctime = os.stat(os.path.join(svc, 'log', 'data',
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
                fname = os.path.join(tm_env().running_dir, instance, 'data',
                                     'state.json')
            else:
                fname = os.path.join(
                    _app_path(tm_env(), instance, uniq), 'data', 'state.json')

            try:
                with io.open(fname) as f:
                    return json.load(f)
            except EnvironmentError as err:
                if uniq == 'running' or err.errno != errno.ENOENT:
                    raise

                fname = _archive_path(tm_env(), 'sys', instance, uniq)
                with tarfile.open(fname) as archive:
                    member = archive.extractfile('state.json')
                    return json.load(member)

        class _ArchiveAPI(object):
            """Access to archive files."""

            def __init__(self):

                def _get(archive_id):
                    """Get arch file path."""
                    instance, uniq, arch_type = archive_id.split('/')
                    arch_path = _archive_path(tm_env(), arch_type, instance,
                                              uniq)
                    if not os.path.exists(arch_path):
                        raise exc.LocalFileNotFoundError(
                            '{} cannot be found.'.format(arch_path))

                    return arch_path

                self.get = _get

        self.list = _list
        self.get = _get
        self.log = mk_logapi(tm_env)()
        self.archive = _ArchiveAPI()
        self.metrics = mk_metrics_api(tm_env)()


def init(_authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return api
