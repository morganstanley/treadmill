"""Utilities for caching cell data to file.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import errno
import hashlib
import io
import logging
import os
import tempfile

import kazoo.exceptions
import six

from treadmill import fs
from treadmill import utils
from treadmill import zkutils
from treadmill import zknamespace as z

_ZK_DATA_SIZE_LIMIT = utils.size_to_bytes('1M')

_LOGGER = logging.getLogger(__name__)


class ZkCachedEntry(collections.namedtuple('_ZkCachedEntry',
                                           ['fname', 'chksum', 'ctime'])):
    """Entry in the local data cache.
    """


class ZkDataEntry(collections.namedtuple('_ZkDataEntry',
                                         ['zname', 'chksum', 'seq'])):
    """Entry in the Zookeeper store.
    """


class ZkDataCache:
    """Manage ZK data cached locally.

    Files are always added locally first (ensuring proper chksum calculation).
    Adding the same file twice is a noop (besides chksum).

    push / pull operations compare files and chksum and minimize transfert.

    Easily integrates with a ChildrenWatch to automatically refresh cache on
    Zookeeper changes.
    """
    _LCL_FILE_FMT = '{name}#{chksum}'

    __slots__ = (
        '_cached',
        '_localpath',
        '_zkclient',
        '_zkdata',
        '_zkpath',
    )

    def __init__(self, zkclient, zkpath, localpath):
        self._cached = {}
        self._localpath = localpath
        self._zkclient = None
        self._zkdata = {}
        self._zkpath = zkpath

        self.refresh_cache()
        if zkclient is not None:
            self.zkclient = zkclient

    @property
    def cached(self):
        """Dictionary of name to list of ZkCachedEntry.
        """
        return self._cached

    @property
    def zkdata(self):
        """Dictionary of name to list of ZkDataEntry.
        """
        return self._zkdata

    @property
    def zkclient(self):
        """the Zookeeper client of the cache.
        """
        return self._zkclient

    @zkclient.setter
    def zkclient(self, new_client):
        """Define the Zookeeper client for the cache.
        """
        self._zkclient = new_client
        if new_client is not None:
            self.refresh_zk()

    def refresh_cache(self):
        """Refresh the cache from files present in localdir.

        Assume a dirty directory with duplicate files.
        """
        found = {}
        for fname in os.listdir(self._localpath):
            if '#' not in fname:
                _LOGGER.warning('Bad file in cache dir: %r', fname)
                continue

            (name, chksum) = fname.split('#', 1)
            final_filename = os.path.join(self._localpath, fname)
            fname_stat = os.stat(final_filename)
            found.setdefault(name, []).append(
                ZkCachedEntry(
                    fname=final_filename,
                    chksum=chksum,
                    ctime=fname_stat.st_ctime
                )
            )
        for name in found:
            found[name].sort(
                key=lambda e: e.ctime,  # Sort entries by their creation time
                reverse=True
            )

        self._cached = found

    def refresh_zk(self, zknodes=None):
        """Parse data from Zookeeper nodes.

        NOTE: This is intended to be called with the output of a
        `:func:get_children` or in the callback of a `:class:ChildrenWatch`.
        If zknodes is None, get Zookeeper nodes first and then parse data.
        """
        if zknodes is None:
            try:
                zknodes = self._zkclient.get_children(self._zkpath)
            except kazoo.exceptions.NoNodeError:
                zknodes = []

        data = {}
        for node in zknodes:
            (name, chksum, seq) = node.split('#', 2)
            data.setdefault(name, []).append(
                ZkDataEntry(
                    zname=z.join_zookeeper_path(self._zkpath, node),
                    chksum=chksum,
                    seq=int(seq)
                )
            )
        for name in data:
            data[name].sort(
                key=lambda e: e.seq,  # Sort nodes by their sequence numbers
                reverse=True
            )

        self._zkdata = data

    def add_data(self, name, data):
        """
        :param ``str`` name:
            Name for the data.
        :param ``bytes|generator`` data:
            Data to store in bytes.
        :returns:
            ``str`` - Digest of the added data.
        """
        # Use the in memory or the stream implementation
        if hasattr(data, 'decode'):
            cache_entry = self._add_data_bytes(name, data)
        else:
            cache_entry = self._add_data_stream(name, data)

        if not cache_entry:
            return None

        # New entries are always added at the "top" of the list.
        self._cached.setdefault(name, []).insert(0, cache_entry)
        self._trim_cache(name)

        return cache_entry.chksum

    def rm_data(self, name):
        """Remove data from the cache.

        :param ``str`` name:
            Name for the data.
        """
        entries = self._cached.pop(name, [])
        _LOGGER.info('Removing %r', entries)
        for cache_entry in entries:
            fs.rm_safe(cache_entry.fname)

    def get_data(self, name):
        """Get data from the cache.

        :param ``str`` name:
            Name for the data.
        """
        # The latest data is the one at the top of the stack.
        latest = self._cached[name][0]
        # Return a buffer object to the cache file with a checksum attribute.
        data = io.open(latest.fname, mode='rb')
        data.checksum = latest.chksum

        return data

    def push(self, expunge=False):
        """Push up cache data to Zookeeper.

        :param ``bool`` expunge:
            If `True`, remove all remote files not present locally.
        :returns:
            `True` - When new data was pushed up to Zookeeper.
            `False` - When Zookeeper was already up to date.
        """
        assert self.zkclient is not None, 'Operation requires a ZK client.'

        new_data = False
        for name, entries in six.iteritems(self._cached):
            # We only consider the latest version (in case of dirty cache).
            cache_entry = entries[0]
            zk_entry = (
                self._zkdata[name][0]
                if name in self._zkdata
                else None
            )
            # Upload a new version if the chksum is different.
            if zk_entry is None or cache_entry.chksum != zk_entry.chksum:
                with io.open(cache_entry.fname, 'rb') as data:
                    self.zkclient.create(
                        '{path}/{name}#{chksum}#'.format(
                            path=self._zkpath,
                            name=name,
                            chksum=cache_entry.chksum
                        ),
                        data.read(),
                        sequence=True,
                        makepath=True
                    )
                new_data = True

        if new_data:
            self.refresh_zk()

        for name, entries in list(six.viewitems(self._zkdata)):
            if name not in self._cached:
                if expunge:
                    # Clean up all sequence numbers for that name.
                    for zk_entry in entries:
                        zkutils.ensure_deleted(self.zkclient, zk_entry.zname)
            else:
                # Clean up all "older" sequence numbers for that name.
                for zk_entry in entries[1:]:
                    zkutils.ensure_deleted(self.zkclient, zk_entry.zname)

        return new_data

    def pull(self, expunge=False, refresh=False):
        """Compare files and chksum with nodes in Zookeeper.

        Pull down data from Zookeeper into the cache if files and nodes differ.

        :param ``bool`` expunge:
            If `True`, remove all local files not present upstream.

        :param ``bool`` refresh:
            If `True`, refresh the list of Zookeeper nodes.

        :returns:
            `True` - When new local data was pulled down.
            `False` - When local data is already up to date.
        """
        assert self.zkclient is not None, 'Operation requires a ZK client.'

        if refresh:
            self.refresh_zk()

        new_data = False
        for name, entries in six.iteritems(self._zkdata):
            # We only consider the latest version (in case of dirty cache).
            zk_entry = entries[0]
            cache_entry = (
                self._cached[name][0]
                if name in self._cached
                else None
            )
            # Download a new version if the chksum is different.
            if cache_entry is None or zk_entry.chksum != cache_entry.chksum:
                (data, _metadata) = self.zkclient.get(zk_entry.zname)
                # Store the new cached entry
                cache_entry = self._add_data_bytes(name, data,
                                                   chksum=zk_entry.chksum)
                self._cached.setdefault(name, []).insert(
                    0,
                    cache_entry
                )
                new_data = True

        for name in list(six.viewkeys(self._cached)):
            if name not in self._zkdata:
                if expunge:
                    self.rm_data(name)
            else:
                self._trim_cache(name)

        return new_data

    def _add_data_stream(self, name, data):
        """Add stream data to the cache.

        :param ``str`` name:
            Name for the data.
        :param ``generator`` data:
            Data to store.
        """
        hash_object = hashlib.sha1()
        try:
            with tempfile.NamedTemporaryFile(dir=self._localpath,
                                             prefix='.tmpXXX_{}'.format(name),
                                             mode='wb', delete=False) as tmp:
                for chunk in data:
                    hash_object.update(chunk)
                    tmp.write(chunk)

            chksum = hash_object.hexdigest()

            final_filename = os.path.join(
                self._localpath,
                self._LCL_FILE_FMT.format(
                    name=name,
                    chksum=chksum
                )
            )
            os.link(tmp.name, final_filename)
            ctime = os.stat(final_filename).st_ctime

            res = ZkCachedEntry(
                fname=final_filename,
                chksum=chksum,
                ctime=ctime
            )

        except OSError as err:
            if err.errno == errno.EEXIST:
                res = None
            else:
                raise

        finally:
            os.unlink(tmp.name)

        return res

    def _add_data_bytes(self, name, data, chksum=None):
        """Add a data array (in memory) to the cache.

        :param ``str`` name:
            Name for the data.
        :param ``bytes`` data:
            Data to store.
        """
        if chksum is None:
            chksum = hashlib.sha1(data).hexdigest()

        final_filename = os.path.join(
            self._localpath,
            self._LCL_FILE_FMT.format(
                name=name,
                chksum=chksum
            )
        )
        # Optimization: return fast
        try:
            os.stat(final_filename)
            return None

        except OSError as err:
            if err.errno == errno.ENOENT:
                pass
            else:
                raise

        # Add a new file
        try:
            with tempfile.NamedTemporaryFile(dir=self._localpath,
                                             prefix='.tmpXXX_{}'.format(name),
                                             mode='wb', delete=False) as tmp:
                tmp.write(data)

            os.link(tmp.name, final_filename)
            ctime = os.stat(final_filename).st_ctime

        finally:
            os.unlink(tmp.name)

        return ZkCachedEntry(
            fname=final_filename,
            chksum=chksum,
            ctime=ctime
        )

    def _trim_cache(self, name):
        """Cleanup the cache ensuring only the latest versions are
        present.

        :param ``str`` name:
            Key name for the data.
        """
        cached = self._cached[name]
        if len(cached) == 1:
            return

        self._cached[name], extra = cached[:1], cached[1:]
        _LOGGER.debug('Trimming %r', extra)
        for cache_entry in extra:
            fs.rm_safe(cache_entry.fname)


__all__ = [
    'ZkDataCache',
]
