"""Implementation of allocation API."""
from __future__ import absolute_import

import glob
import errno
import logging
import os
import tarfile

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

        def _archives(archive_type, instance):
            """Returns list of (time, fname) ordered recent first."""
            archives = []
            name, instance_id = instance.rsplit('#', 1)
            pattern = '%s-%s-*.%s.tar.gz' % (name, instance_id, archive_type)

            archive_glob = os.path.join(app_env().archives_dir, pattern)
            for fname in glob.glob(archive_glob):
                ctime = os.stat(fname).st_ctime
                archives.append((ctime, fname))

            return sorted(archives, reverse=True)

        class _RunningAPI(object):
            """Running API."""

            def __init__(self):

                def _list():
                    """List running containers."""
                    result = []
                    running_glob = os.path.join(app_env().running_dir, '*')
                    for running in glob.glob(running_glob):
                        try:
                            app_path = os.readlink(running)
                            result.append({
                                '_id': os.path.basename(running),
                                'uniq_name': os.path.basename(app_path),
                                'ctime': os.stat(app_path).st_ctime
                            })
                        except OSError as oserr:
                            if oserr.errno == errno.ENOENT:
                                continue

                            raise
                    return result

                def get(instance):
                    """Get running instance info."""
                    app_path = os.readlink(os.path.join(app_env().running_dir,
                                                        instance))
                    return {
                        '_id': instance,
                        'uniq_name': os.path.basename(app_path),
                        'ctime': os.stat(app_path).st_ctime
                    }

                def lines(instance, logtype, component):
                    """Yields lines from the log file."""

                    fname = os.path.join(
                        app_env().running_dir,
                        instance,
                        logtype,
                        component,
                        'log',
                        'current'
                    )

                    with open(fname) as f:
                        for line in f:
                            yield line

                self.list = _list
                self.get = get
                self.lines = lines

        class _ArchiveAPI(object):
            """Archive API."""

            def __init__(self):

                def _list(archive_type, instance):
                    """List all archives."""
                    archives = _archives(archive_type, instance)
                    return [{'_id': '%s/%s' % (instance, idx),
                             'instance': instance,
                             'ctime': item[0]}
                            for idx, item in enumerate(archives)]

                def get(archive_type, instance, idx):
                    """Archive details."""
                    _LOGGER.info('archive::get - %s, %s, %s', archive_type,
                                 instance, idx)

                    archives = _archives(archive_type, instance)
                    if idx >= len(archives):
                        raise Exception('Invalid index.')

                    ctime, fname = archives[idx]

                    with tarfile.open(fname, 'r:gz') as f:
                        return {
                            '_id': '%s/%s' % (instance, idx),
                            'instance': instance,
                            'ctime': ctime,
                            'content': f.getnames()
                        }

                def lines(archive_type, instance, idx, path):
                    """Stream file from the archive."""
                    archives = _archives(archive_type, instance)
                    if idx >= len(archives):
                        raise Exception('Invalid index.')

                    _ctime, fname = archives[idx]
                    with tarfile.open(fname) as archive:
                        member = archive.extractfile(path)
                        for line in member:
                            yield line

                def path(archive_type, instance, idx):
                    """Return full path of the archive."""
                    archives = _archives(archive_type, instance)
                    if idx >= len(archives):
                        raise Exception('Invalid index.')

                    _ctime, fname = archives[idx]
                    return fname

                self.list = _list
                self.get = get
                self.lines = lines
                self.path = path

        self.running = _RunningAPI()
        self.archive = _ArchiveAPI()


def init(_authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return api
