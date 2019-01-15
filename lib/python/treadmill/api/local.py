"""Implementation of local API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import errno
import fnmatch
import functools
import glob
import io
import json
import logging
import os
import operator
import re
import shutil
import tarfile
import tempfile

import six
from six.moves import _thread

from treadmill import exc
from treadmill import appenv
from treadmill import logcontext as lc
from treadmill import rrdutils

_LOGGER = lc.ContainerAdapter(logging.getLogger(__name__))


def _app_path(tm_env, instance, uniq):
    """Return application path given app env, app id and uniq."""
    return os.path.join(tm_env().apps_dir,
                        '%s-%s' % (instance.replace('#', '-'), uniq))


def _archive_path(tm_env, archive_type, instance, uniq):
    """Return archive path given app env, archive id and type."""
    return os.path.join(tm_env().archives_dir, '%s-%s.%s.tar.gz' %
                        (instance.replace('#', '-'), uniq, archive_type))


def _temp_dir():
    """Construct an empty temporary dir for each thread and return the path."""
    dirname = os.path.join(tempfile.gettempdir(),
                           'local-{}.temp'.format(_thread.get_ident()))

    shutil.rmtree(dirname, True)
    os.mkdir(dirname, 0o755)
    return dirname


def _get_file(file_=None,
              arch=None,
              arch_extract=True,
              arch_extract_filter=None):
    """Return the file pointed by "file_" or extract the specified archive.

    Return file_ if the specified file exists or extract the files specified
    by 'arch_extract_filter' from 'arch' and return the path to the extracted
    file.
    """
    if os.path.exists(file_):
        _LOGGER.info('Returning {}'.format(file_))
        return file_

    if not arch_extract:
        raise exc.LocalFileNotFoundError('{} cannot be found.'.format(file_))

    extracted = _extract_archive(arch, arch_extract_filter)[0]
    _LOGGER.info('Returning {}'.format(extracted))
    return extracted


def _arch_file_filter(arch_members, fname=None):
    """Filter func to return one archive member with name 'fname' of an archive
    """
    return [f for f in arch_members if f.name == fname]


def _arch_log_filter(arch_members, rel_log_dir=None):
    """Filter func to return the log file members of an archive.

    It keeps files that are in "rel_log_dir" and created by s6-log
    ie. 'current' and '@*.s' (rotated log file: @400000847572.s)
    """
    return [f for f in arch_members
            if (os.path.dirname(f.name) == rel_log_dir and (fnmatch.fnmatch(
                os.path.basename(f.name), 'current') or fnmatch.fnmatch(
                    os.path.basename(f.name), '@*.s')))]


def _extract_archive(arch, extract_filter=None):
    """Extract the members filtered by 'extract_filter' from archive
    'arch' and return the path to the extracted files.
    """

    _LOGGER.info('Extract archive {}'.format(arch))
    if not os.path.exists(arch):
        raise exc.LocalFileNotFoundError('{} cannot be found.'.format(arch))

    try:
        # extract the req. paths from the archive to a temp directory
        temp_dir = _temp_dir()
        with tarfile.open(arch) as arch_:
            if extract_filter:
                to_extract = extract_filter(arch_)
            else:
                to_extract = arch_.getmembers()

            arch_.extractall(path=temp_dir, members=to_extract)

    except KeyError as err:
        _LOGGER.error(err)
        raise exc.LocalFileNotFoundError(
            'Error while extracting {}: {}'.format(arch, err))

    return [os.path.join(temp_dir, f.name) for f in to_extract]


def _rel_log_dir_path(logtype, component):
    """The relative path of the log directory for a given execution."""
    if logtype == 'sys':
        return os.path.join('sys', component, 'data', 'log')

    return os.path.join('services', component, 'data', 'log')


def _abs_log_dir_path(tm_env, instance, uniq, rel_log_dir_path):
    """The absolut path of the log directory for a given execution."""
    if uniq == 'running':
        return os.path.join(tm_env().running_dir, instance, 'data',
                            rel_log_dir_path)

    return os.path.join(
        _app_path(tm_env, instance, uniq), 'data', rel_log_dir_path)


def _concat_files(file_lst):
    """Concatenate the files in file_lst and return a file-like obj."""
    _LOGGER.info('Concatenating files: {}'.format(file_lst))
    concatenated = io.BytesIO()
    for file_ in file_lst:
        # Do not abort if a file cannot be opened eg. when the oldest log
        # file is "rotated out" while this log retrieval op. is running
        try:
            with io.open(file_, 'rb') as f:
                shutil.copyfileobj(f, concatenated)
        except IOError as err:
            if err.errno == errno.ENOENT:
                _LOGGER.info('File {} cannot be opened: {}'.format(file_, err))
            else:
                raise

    concatenated.seek(0)

    return io.TextIOWrapper(concatenated, errors='ignore')


def _fragment(iterable, start=0, limit=None):
    """
    Selects a fragment of the iterable and returns the items in 'normal order'.

    The lowest index is 0 and designates the first line of the file.
    'Limit' specifies the number of lines to return.
    """
    # TODO: Naive implementation. Needs to be rewritten to a solution with
    # file pointer moving around etc. if it turns out that this isn't
    # performant enough.
    if limit is not None and limit >= 0:
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
                __name__, 'Index start=%s is out of range.' % str(start))

        return fragment

    try:
        for _ in six.moves.range(start):
            six.next(iterable)
    except StopIteration:
        raise exc.InvalidInputError(
            __name__, 'Index start=%s is out of range.' % str(start))

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
    if limit is not None and limit >= 0:
        maxlen = start + limit

    fragment = collections.deque(iterable, maxlen)
    try:
        for _ in six.moves.range(start):
            fragment.pop()
    except IndexError:
        raise exc.InvalidInputError(
            __name__, 'Index start=%s is out of range.' % str(start))

    fragment.reverse()
    return fragment


def mk_metrics_api(tm_env):
    """Factory to create metrics api.
    """

    class _MetricsAPI:
        """Acess to the locally gathered metrics.
        """

        def __init__(self):

            def _get(rsrc_id, timeframe, as_json=False):
                """Return the rrd metrics.
                """
                with lc.LogContext(_LOGGER, rsrc_id):
                    _LOGGER.info('Get metrics')
                    id_ = self._unpack_id(rsrc_id)
                    file_ = self._get_rrd_file(**id_)

                    if as_json:
                        return rrdutils.get_json_metrics(file_, timeframe)

                    return file_

            def _file_path(rsrc_id):
                """Return the rrd metrics file path.
                """
                id_ = self._unpack_id(rsrc_id)

                return self._abs_met_path(**id_)

            self.file_path = _file_path
            self.get = _get

        def _remove_ext(self, fname, extension='.rrd'):
            """Returns the basename of a file without the extension.
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

        def _get_rrd_file(self,
                          service=None,
                          app=None,
                          uniq=None,
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
            return _get_file(
                self._abs_met_path(app=app, uniq=uniq),
                arch_extract=arch_extract,
                arch=_archive_path(tm_env, 'sys', app, uniq),
                arch_extract_filter=functools.partial(_arch_file_filter,
                                                      fname='metrics.rrd'))

        def _core_rrd_file(self, service):
            """Return the given service's rrd file."""
            return _get_file(self._abs_met_path(service), arch_extract=False)

        def _abs_met_path(self, service=None, app=None, uniq=None):
            """Return the rrd metrics file's full path."""
            if service is not None:
                return os.path.join(tm_env().metrics_dir, 'core',
                                    service + '.rrd')

            return os.path.join(tm_env().metrics_dir, 'apps',
                                '%s-%s.rrd' % (app.replace('#', '-'), uniq))

    return _MetricsAPI


def mk_logapi(tm_env):
    """Factory  for log api.
    """

    class _LogAPI:
        """Access to log files.
        """

        def __init__(self):

            def _get(log_id, start=0, limit=None, order=None):
                """Get log file.
                """
                instance, uniq, logtype, component = log_id.split('/')
                with lc.LogContext(_LOGGER, '{}/{}'.format(instance, uniq)):
                    log_f = self._get_logfile(instance, uniq, logtype,
                                              component)

                    _LOGGER.info('Requested {} items starting from line {} '
                                 'in {} order'.format(limit, start, order))

                    if start is not None and start < 0:
                        raise exc.InvalidInputError(
                            __name__,
                            'Index cannot be less than 0, got: {}'.format(
                                start))

                    with io.open(log_f, 'rt', errors='ignore') as log:
                        if order == 'desc':
                            return _fragment_in_reverse(log, start, limit)

                        return _fragment(log, start, limit)

            def _get_all(log_id):
                """Return a file-like object with all the log entries including
                the rotated ones.
                """
                instance, uniq, logtype, component = log_id.split('/')

                with lc.LogContext(_LOGGER, '{}/{}'.format(instance, uniq)):
                    rel_log_dir = _rel_log_dir_path(logtype, component)
                    abs_log_dir = _abs_log_dir_path(tm_env, instance, uniq,
                                                    rel_log_dir)

                    _LOGGER.info('Check logs in {}'.format(abs_log_dir))
                    if os.path.exists(abs_log_dir):
                        logs = glob.glob(os.path.join(abs_log_dir, '@*.s'))
                        logs.append(os.path.join(abs_log_dir, 'current'))

                        # alphanumerical sort results in chronological order
                        # as per
                        # https://skarnet.org/software/skalibs/libstddjb/tai.html
                        return _concat_files(sorted(logs))

                    if uniq == 'running':
                        raise exc.LocalFileNotFoundError(
                            'No log could be found for {}.'.format(log_id))

                    logs = _extract_archive(
                        _archive_path(tm_env, logtype, instance, uniq),
                        extract_filter=functools.partial(
                            _arch_log_filter,
                            rel_log_dir=rel_log_dir))

                    # alphanumerical sort results in chronological order
                    # as per
                    # https://skarnet.org/software/skalibs/libstddjb/tai.html
                    return _concat_files(sorted(logs))

            self.get = _get
            self.get_all = _get_all

        def _get_logfile(self, instance, uniq, logtype, comp):
            """Return the corresponding log file."""
            _LOGGER.info('Log: %s %s %s %s', instance, uniq, logtype, comp)
            try:
                return self._get_logfile_new(instance, uniq, logtype, comp)
            except exc.LocalFileNotFoundError:
                return self._get_logfile_old(instance, uniq, logtype, comp)

        def _get_logfile_new(self, instance, uniq, logtype, component):
            """Return the log file according to the newer file layout.
            """

            if logtype == 'sys':
                rel_log_path = os.path.join('sys', component, 'data', 'log',
                                            'current')
            else:
                rel_log_path = os.path.join('services', component, 'data',
                                            'log', 'current')

            if uniq == 'running':
                abs_log_path = os.path.join(tm_env().running_dir, instance,
                                            'data', rel_log_path)
            else:
                abs_log_path = os.path.join(
                    _app_path(tm_env, instance, uniq), 'data', rel_log_path)

            _LOGGER.info('Logfile: %s', abs_log_path)

            return _get_file(
                abs_log_path,
                arch=_archive_path(tm_env, logtype, instance, uniq),
                arch_extract=bool(uniq != 'running'),
                arch_extract_filter=functools.partial(_arch_file_filter,
                                                      fname=rel_log_path))

        def _get_logfile_old(self, instance, uniq, logtype, component):
            """Return the log file according to the old file layout.
            """
            # TODO: method should be deleted once the old containers disappear

            if logtype == 'sys':
                rel_log_path = os.path.join('sys', component, 'log', 'current')
            else:
                rel_log_path = os.path.join('services', component, 'log',
                                            'current')

            if uniq == 'running':
                abs_log_path = os.path.join(tm_env().running_dir, instance,
                                            rel_log_path)
            else:
                abs_log_path = os.path.join(
                    _app_path(tm_env, instance, uniq), rel_log_path)

            _LOGGER.info('Logfile: %s', abs_log_path)

            return _get_file(
                abs_log_path,
                arch=_archive_path(tm_env, logtype, instance, uniq),
                arch_extract=bool(uniq != 'running'),
                arch_extract_filter=functools.partial(_arch_file_filter,
                                                      fname=rel_log_path))

    return _LogAPI


class API:
    """Treadmill Local REST api.
    """
    # pylint: disable=too-many-statements

    def __init__(self):

        self._tm_env = None

        def tm_env(_metrics_api=None):
            """Lazy instantiate app environment.
            """
            if not self._tm_env:
                # TODO: we need to pass this parameter to api, unfortunately
                #       in current api framework it is not trivial.
                approot = os.environ['TREADMILL_APPROOT']
                _LOGGER.info('Using approot: %s', approot)
                self._tm_env = appenv.AppEnvironment(approot)

            return self._tm_env

        def _replace(app_name):
            """Replace application's name format (i.e. '$name#$instance') with
               glob file format (i.e. '$name-$instance').
            """
            return '-'.join(app_name.rsplit('#', 1))

        def _get_running(path_name):
            """Get running instance.
            """
            try:
                app_path = os.readlink(path_name)
                full_name = os.path.basename(app_path)
                name, instance, uniq = full_name.rsplit('-', 2)
                ctime = os.stat(app_path).st_ctime
                return {
                    full_name: {
                        '_id': '%s#%s/%s' % (name, instance, uniq),
                        'ctime': ctime,
                        'state': 'running',
                    }
                }

            except OSError as err:
                if err.errno == errno.ENOENT:
                    _LOGGER.info('pathname %s does not exist.', path_name)
                else:
                    _LOGGER.warning(
                        'Unable to get running instance: %s', str(err)
                    )

            return None

        def _list_running(app_name=None):
            """List all running instances.

            :param app_name: application's full name, i.e. '$name#$instance'.
            """
            pattern = '*' if app_name is None else app_name
            running_glob = os.path.join(tm_env().running_dir, pattern)

            result = {}
            for path_name in glob.glob(running_glob):
                data = _get_running(path_name)
                if data is not None:
                    result.update(data)

            return result

        def _get_finished(path_name):
            """Get finished instance.
            """
            try:
                full_name = os.path.basename(path_name)[:-len('.sys.tar.gz')]
                name, instance, uniq = full_name.rsplit('-', 2)
                ctime = os.stat(path_name).st_ctime
                return {
                    full_name: {
                        '_id': '%s#%s/%s' % (name, instance, uniq),
                        'ctime': ctime,
                        'state': 'finished',
                    }
                }

            except OSError as err:
                if err.errno == errno.ENOENT:
                    _LOGGER.info('pathname %s does not exist.', path_name)
                else:
                    _LOGGER.warning(
                        'Unable to get finished instance: %s', str(err)
                    )

            return None

        def _list_finished(app_name=None):
            """List all finished instances.

            :param app_name: application's full name, i.e. '$name#$instance'.
            """
            fmt = '*.sys.tar.gz'
            if app_name is not None:
                # list instances matching '$name-$instance-$uniq.sys.tar.gz'
                fmt = '{}-*.sys.tar.gz'.format(_replace(app_name))
                _LOGGER.debug('list finished instances with pattern: %r', fmt)

            archive_glob = os.path.join(tm_env().archives_dir, fmt)
            sep = r'\\' if os.name == 'nt' else os.sep
            pattern = re.compile(r'''.*{sep}       # archives dir
                                     \w+        # proid
                                     \.         # .
                                     [\w.]+     # app
                                     -\d+       # id
                                     -\w+       # uniq
                                     .sys.tar.gz'''.format(sep=sep), re.X)

            result = {}
            for archive in [f for f in glob.glob(archive_glob)
                            if pattern.match(f)]:
                data = _get_finished(archive)
                if data is not None:
                    result.update(data)

            return result

        def _list_services():
            """List the local services.
            """
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

        def _list(state=None, inc_svc=False, app_name=None):
            """List all instances on the node.
            """
            result = {}
            if state is None or state == 'running':
                result.update(_list_running(app_name=app_name))
                if inc_svc:
                    result.update(_list_services())
            if state is None or state == 'finished':
                result.update(_list_finished(app_name=app_name))

            values = list(result.values())
            values.sort(
                key=operator.itemgetter('state', 'ctime'),
                reverse=True,
            )
            return values

        # TODO: implementation of this is placeholder, need to think about
        #       more relevant info.
        def _get(uniqid):
            """Get instance info.
            """
            instance, uniq = uniqid.split('/')
            if uniq == 'running':
                fname = os.path.join(tm_env().running_dir, instance, 'data',
                                     'state.json')
            else:
                fname = os.path.join(
                    _app_path(tm_env, instance, uniq), 'data', 'state.json')

            try:
                with io.open(fname) as f:
                    return json.load(f)
            except (OSError, IOError) as err:
                if uniq == 'running' or err.errno != errno.ENOENT:
                    raise

                fname = _archive_path(tm_env, 'sys', instance, uniq)
                with tarfile.open(fname) as archive:
                    member = archive.extractfile('state.json')
                    return json.loads(member.read().decode())

        class _ArchiveAPI:
            """Access to archive files.
            """

            def __init__(self):

                def _get(archive_id):
                    """Get arch file path.
                    """
                    instance, uniq, arch_type = archive_id.split('/')
                    arch_path = _archive_path(tm_env, arch_type, instance,
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
