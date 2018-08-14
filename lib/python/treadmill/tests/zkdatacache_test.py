"""Tests for the ZkDataCache.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import hashlib
import io
import os
import shutil
import tempfile
import unittest

import kazoo
import kazoo.client
import kazoo.exceptions
import mock

import treadmill
import treadmill.context
from treadmill import zkdatacache

from treadmill.tests.testutils import mockzk


class ZkDataCacheTest(mockzk.MockZookeeperTestCase):
    """Tests for the Zookeeper data cache.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.cachedir = os.path.join(self.root, 'cache')
        os.mkdir(self.cachedir)

        treadmill.context.GLOBAL.cell = 'test'
        treadmill.context.GLOBAL.zk.url = 'zookeeper://xxx@yyy:123'

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('treadmill.zkdatacache.ZkDataCache.refresh_cache',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.zkdatacache.ZkDataCache.refresh_zk',
                mock.Mock(set_spec=True))
    def test_zkclient_property_setter(self):
        """Test zkclient property setter.
        """
        zdc = zkdatacache.ZkDataCache(None, '/zk/path', self.cachedir)
        zkclient = kazoo.client.KazooClient()

        zdc.zkclient = zkclient

        zdc.refresh_zk.assert_called_once_with()

    @mock.patch('treadmill.zkdatacache.ZkDataCache.refresh_cache',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.zkdatacache.ZkDataCache.refresh_zk',
                mock.Mock(set_spec=True))
    def test_init(self):
        """Test different options for the constructor.
        """
        # Test init without zkclient.
        zdc = zkdatacache.ZkDataCache(None, '/zk/path', self.cachedir)

        self.assertEqual(
            zdc.zkdata,
            {}
        )
        self.assertEqual(
            zdc.cached,
            {}
        )
        zkdatacache.ZkDataCache.refresh_cache.assert_called_once_with()
        zkdatacache.ZkDataCache.refresh_zk.assert_not_called()

        zkdatacache.ZkDataCache.refresh_cache.reset_mock()
        zkdatacache.ZkDataCache.refresh_zk.reset_mock()

        # Test init with zkclient.
        zkclient = kazoo.client.KazooClient()

        zdc = zkdatacache.ZkDataCache(zkclient, '/zk/path', self.cachedir)

        zkdatacache.ZkDataCache.refresh_cache.assert_called_once_with()
        zdc.refresh_zk.assert_called_once_with()

    @mock.patch('kazoo.client.KazooClient.get_children',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.zkdatacache.ZkDataCache.refresh_cache',
                mock.Mock(set_spec=True))
    def test_refresh_zk(self):
        """Test parsing data from Zookeeper.
        """
        # Test calling with a list of nodes.
        zdc = zkdatacache.ZkDataCache(None, '/zk/path', self.cachedir)

        zdc.refresh_zk(
            [
                'TEST#0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33#00000042',
                'TEST#0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33#00000043',
                'FOO#some_check#00000039',
                'BAR#other_check#00000044',
            ]
        )

        self.assertEqual(
            zdc.zkdata,
            {
                'TEST': [
                    zkdatacache.ZkDataEntry(
                        zname=(
                            '/zk/path/TEST#'
                            '0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33#00000043'
                        ),
                        chksum='0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33',
                        seq=43
                    ),
                    zkdatacache.ZkDataEntry(
                        zname=(
                            '/zk/path/TEST#'
                            '0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33#00000042'
                        ),
                        chksum='0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33',
                        seq=42
                    ),
                ],
                'BAR': [
                    zkdatacache.ZkDataEntry(
                        zname='/zk/path/BAR#other_check#00000044',
                        chksum='other_check',
                        seq=44
                    ),
                ],
                'FOO': [
                    zkdatacache.ZkDataEntry(
                        zname='/zk/path/FOO#some_check#00000039',
                        chksum='some_check',
                        seq=39
                    ),
                ],
            }
        )

        # Test getting a list of nodes.
        zkclient = kazoo.client.KazooClient()
        zkclient.get_children.return_value = [
            'TEST#0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33#00000042',
            'TEST#0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33#00000043',
            'FOO#some_check#00000039',
            'BAR#other_check#00000044',
        ]
        zdc = zkdatacache.ZkDataCache(zkclient, '/zk/path', self.cachedir)

        zdc.refresh_zk()

        self.assertEqual(
            zdc.zkdata,
            {
                'TEST': [
                    zkdatacache.ZkDataEntry(
                        zname=(
                            '/zk/path/TEST#'
                            '0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33#00000043'
                        ),
                        chksum='0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33',
                        seq=43
                    ),
                    zkdatacache.ZkDataEntry(
                        zname=(
                            '/zk/path/TEST#'
                            '0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33#00000042'
                        ),
                        chksum='0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33',
                        seq=42
                    ),
                ],
                'BAR': [
                    zkdatacache.ZkDataEntry(
                        zname='/zk/path/BAR#other_check#00000044',
                        chksum='other_check',
                        seq=44
                    ),
                ],
                'FOO': [
                    zkdatacache.ZkDataEntry(
                        zname='/zk/path/FOO#some_check#00000039',
                        chksum='some_check',
                        seq=39
                    ),
                ],
            }
        )

        # Test NoNodeError while getting a list of nodes.
        zkclient.get_children.side_effect = kazoo.exceptions.NoNodeError
        zdc = zkdatacache.ZkDataCache(zkclient, '/zk/path', self.cachedir)

        zdc.refresh_zk()

        self.assertEqual(zdc.zkdata, {})

    @mock.patch('io.open', mock.mock_open(), create=True)
    @mock.patch('os.listdir', mock.Mock(set_spec=True))
    @mock.patch('os.stat', mock.Mock(set_spec=True))
    def test_refresh_cache(self):
        """Test refresh of local cache data.
        """
        os.listdir.return_value = []
        zdc = zkdatacache.ZkDataCache(None, '/zk/path', self.cachedir)

        zdc.refresh_cache()

        self.assertEqual(
            zdc.cached,
            {}
        )

        os.listdir.return_value = [
            'TEST#0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33',
            'TEST#0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33',
            'FOO#some_check',
            'BAR#other_check',
            'bad_file',
        ]
        os.stat.side_effect = [
            os.stat_result((42,) * 10),
            os.stat_result((43,) * 10),
            os.stat_result((44,) * 10),
            os.stat_result((45,) * 10),
        ]

        zdc.refresh_cache()

        os.stat.assert_has_calls(
            [
                mock.call(
                    os.path.join(
                        self.cachedir,
                        'TEST#0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33'
                    )
                ),
                mock.call(
                    os.path.join(
                        self.cachedir,
                        'TEST#0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33',
                    )
                ),
                mock.call(
                    os.path.join(
                        self.cachedir,
                        'FOO#some_check',
                    )
                ),
                mock.call(
                    os.path.join(
                        self.cachedir,
                        'BAR#other_check',
                    )
                ),
            ]
        )
        self.assertEqual(
            zdc.cached,
            {
                'TEST': [
                    zkdatacache.ZkCachedEntry(
                        fname=os.path.join(
                            self.cachedir,
                            'TEST#0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33'
                        ),
                        chksum='0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33',
                        ctime=43
                    ),
                    zkdatacache.ZkCachedEntry(
                        fname=os.path.join(
                            self.cachedir,
                            'TEST#0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33'
                        ),
                        chksum='0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33',
                        ctime=42
                    ),
                ],
                'BAR': [
                    zkdatacache.ZkCachedEntry(
                        fname=os.path.join(
                            self.cachedir,
                            'BAR#other_check'
                        ),
                        chksum='other_check',
                        ctime=45
                    ),
                ],
                'FOO': [
                    zkdatacache.ZkCachedEntry(
                        fname=os.path.join(
                            self.cachedir,
                            'FOO#some_check'
                        ),
                        chksum='some_check',
                        ctime=44
                    ),
                ],
            }
        )

    @mock.patch('treadmill.fs.rm_safe', mock.Mock(set_spec=True))
    def test__trim_cache(self):
        """Test _trim operation leaves the right number of entries in the
        cache.
        """
        # pylint: disable=protected-access

        zdc = zkdatacache.ZkDataCache(None, '/zk/path', self.cachedir)
        zdc._cached = {}
        self.assertRaises(
            KeyError,
            zdc._trim_cache,
            'does not exists'
        )
        self.assertEqual(
            zdc._cached,
            {}
        )
        treadmill.fs.rm_safe.assert_not_called()
        treadmill.fs.rm_safe.reset_mock()

        zdc._cached = {
            'TEST': [
                zkdatacache.ZkCachedEntry(
                    fname='a#chk2', chksum='chk2', ctime='0'
                ),
                zkdatacache.ZkCachedEntry(
                    fname='a#chk1', chksum='chk1', ctime='0'
                ),
            ],
        }
        zdc._trim_cache('TEST')
        self.assertEqual(
            zdc._cached,
            {
                'TEST': [
                    zkdatacache.ZkCachedEntry(
                        fname='a#chk2', chksum='chk2', ctime='0'
                    ),
                ]
            }
        )
        treadmill.fs.rm_safe.assert_called_with('a#chk1')
        treadmill.fs.rm_safe.reset_mock()

    def test__add_data_stream(self):
        """Chech adding a data stream to the cache.
        """
        # pylint: disable=protected-access

        zdc = zkdatacache.ZkDataCache(None, '/zk/path', self.cachedir)
        test_data = b'some test data'
        test_chksum = hashlib.sha1(test_data).hexdigest()

        res = zdc._add_data_stream('TEST', io.BytesIO(test_data))

        self.assertEqual(
            res,
            (
                os.path.join(self.cachedir, 'TEST#{}'.format(test_chksum)),
                test_chksum,
                mock.ANY,
            )
        )

    @mock.patch('os.link', mock.Mock(set_spec=True))
    def test__add_data_stream_exists(self):
        """Check adding the same data stream twice returns None.
        """
        # pylint: disable=protected-access

        zdc = zkdatacache.ZkDataCache(None, '/zk/path', self.cachedir)
        test_data = b'some test data'
        os.link.side_effect = OSError(errno.EEXIST, 'Already there')

        res = zdc._add_data_stream('TEST', io.BytesIO(test_data))

        self.assertIsNone(res)

    @mock.patch('os.stat', mock.Mock(set_spec=True))
    def test__add_data_bytes(self):
        """Test adding bytes data to the cache.
        """
        # pylint: disable=protected-access

        os.stat.side_effect = [
            OSError(errno.ENOENT, 'No such file'),
            os.stat_result((42,) * 10),
        ]

        zdc = zkdatacache.ZkDataCache(None, '/zk/path', self.cachedir)
        test_data = b'some test data'
        test_chksum = hashlib.sha1(test_data).hexdigest()

        res1 = zdc._add_data_bytes('TEST', test_data)

        self.assertEqual(
            res1,
            (
                os.path.join(self.cachedir, 'TEST#{}'.format(test_chksum)),
                test_chksum,
                42,
            )
        )
        os.stat.reset_mock()

        # Check adding the same data twice returns None.
        os.stat.side_effect = os.stat_result((42,) * 10)

        res2 = zdc._add_data_bytes('TEST', test_data)

        self.assertIsNone(res2)
        os.stat.reset_mock()

        # Check we can force a precalculated chksum
        os.stat.side_effect = [
            OSError(errno.ENOENT, 'No such file'),
            os.stat_result((43,) * 10),
        ]
        res = zdc._add_data_bytes('TEST', test_data, chksum='preset_chksum')

        self.assertEqual(
            res,
            (
                os.path.join(self.cachedir, 'TEST#{}'.format('preset_chksum')),
                'preset_chksum',
                43,
            )
        )

    @mock.patch('io.open', mock.mock_open(), create=True)
    def test_get_data(self):
        """Test cache data retrieaval.
        """
        # pylint: disable=protected-access

        zdc = zkdatacache.ZkDataCache(None, '/zk/path', self.cachedir)

        # Asking for non-existent items.
        zdc._cached = {}
        self.assertRaises(
            KeyError,
            zdc.get_data,
            'not there'
        )

        # Asking for data.
        zdc._cached = {
            'TEST': [
                zkdatacache.ZkCachedEntry(
                    fname='a#chk2', chksum='chk2', ctime='0'
                ),
            ]
        }

        res = zdc.get_data('TEST')

        io.open.assert_called_with('a#chk2', mode='rb')
        mock_file = io.open.return_value
        self.assertEqual(
            res,
            mock_file
        )
        self.assertEqual(
            mock_file.checksum,
            'chk2'
        )

    @mock.patch('treadmill.fs.rm_safe', mock.Mock(spec_set=True))
    def test_rm_data(self):
        """Test deletion of cache data entry.
        """
        # pylint: disable=protected-access

        zdc = zkdatacache.ZkDataCache(None, '/zk/path', self.cachedir)

        # Deleting non-existent items.
        zdc._cached = {}
        zdc.rm_data('not there')

        treadmill.fs.rm_safe.assert_not_called()
        treadmill.fs.rm_safe.reset_mock()

        # Asking for data.
        zdc._cached = {
            'TEST': [
                zkdatacache.ZkCachedEntry(
                    fname='a#chk2', chksum='chk2', ctime='0'
                ),
                zkdatacache.ZkCachedEntry(
                    fname='a#chk1', chksum='chk1', ctime='0'
                ),
            ],
        }
        zdc.rm_data('TEST')

        self.assertEqual(
            zdc._cached,
            {}
        )
        treadmill.fs.rm_safe.assert_has_calls(
            [
                mock.call('a#chk1'),
                mock.call('a#chk2'),
            ],
            any_order=True
        )
        treadmill.fs.rm_safe.reset_mock()

    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock(set_spec=True))
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock(set_spec=True))
    @mock.patch('kazoo.client.KazooClient.get_children',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.zkdatacache.ZkDataCache._add_data_bytes',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.zkdatacache.ZkDataCache.rm_data',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.zkdatacache.ZkDataCache._trim_cache',
                mock.Mock(set_spec=True))
    def test_pull(self):
        """Test pulling data from Zookeeper into the cache.
        """
        # pylint: disable=protected-access

        zk_content = {
            'zk': {
                'path': {
                    'TEST#0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33#00000042': (
                        b'foo'
                    )
                }
            }
        }
        self.make_mock_zk(zk_content)
        zkclient = treadmill.zkutils.ZkClient()
        test_cache_entry = zkdatacache.ZkCachedEntry(
            fname='TEST#0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33',
            chksum='0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33',
            ctime='0'
        )
        zkdatacache.ZkDataCache._add_data_bytes.return_value = test_cache_entry
        zdc = zkdatacache.ZkDataCache(zkclient, '/zk/path', self.cachedir)
        zdc._cached = {
            'FOO': [
                zkdatacache.ZkCachedEntry(
                    fname='a#chk2', chksum='chk2', ctime='0'
                ),
                zkdatacache.ZkCachedEntry(
                    fname='a#chk1', chksum='chk1', ctime='0'
                ),
            ]
        }

        # Test "normal" pulling.
        zdc.pull()

        zkclient.get.assert_called_with(
            (
                '/zk/path/TEST#'
                '0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33#00000042'
            )
        )
        zdc._add_data_bytes.assert_called_with(
            'TEST',
            b'foo',
            chksum='0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33'
        )
        zdc._trim_cache.assert_called_once_with('TEST')
        self.assertEqual(
            zdc._cached,
            {
                'TEST': [
                    test_cache_entry
                ],
                'FOO': [
                    zkdatacache.ZkCachedEntry(
                        fname='a#chk2', chksum='chk2', ctime='0'
                    ),
                    zkdatacache.ZkCachedEntry(
                        fname='a#chk1', chksum='chk1', ctime='0'
                    ),
                ],
            }
        )
        zdc.rm_data.assert_not_called()
        zkclient.get.reset_mock()
        zkclient.get_children.reset_mock()
        zkclient.exists.reset_mock()
        zdc._add_data_bytes.reset_mock()
        zdc._trim_cache.reset_mock()
        zdc.rm_data.reset_mock()

        # Second pull should result in noop
        zdc.pull()

        zdc._add_data_bytes.assert_not_called()
        zdc.rm_data.assert_not_called()
        zdc._trim_cache.assert_called_once_with('TEST')
        self.assertEqual(
            zdc._cached,
            {
                'TEST': [
                    test_cache_entry
                ],
                'FOO': [
                    zkdatacache.ZkCachedEntry(
                        fname='a#chk2', chksum='chk2', ctime='0'
                    ),
                    zkdatacache.ZkCachedEntry(
                        fname='a#chk1', chksum='chk1', ctime='0'
                    ),
                ],
            }
        )
        zkclient.get.reset_mock()
        zkclient.get_children.reset_mock()
        zkclient.exists.reset_mock()
        zdc._add_data_bytes.reset_mock()
        zdc._trim_cache.reset_mock()
        zdc.rm_data.reset_mock()

        # Pull with expunge should remove all extra entries.
        zdc.pull(expunge=True)

        zdc._add_data_bytes.assert_not_called()
        zdc.rm_data.assert_called_with('FOO')
        zdc._trim_cache.assert_called_with('TEST')

    @mock.patch('io.open', mock.mock_open(read_data=b'foo'), create=True)
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock(set_spec=True))
    @mock.patch('kazoo.client.KazooClient.get_children',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock(set_spec=True))
    def test_push(self):
        """Test pushing data from the cache to Zookeeper.
        """
        # pylint: disable=protected-access

        zkclient = kazoo.client.KazooClient()
        zkclient.get_children.side_effect = [
            [
                'FOO#chk0#0000000039',
                'FOO#chk1#0000000042',
                'BAR#chk_some#0000000040',
                'BAR#chk_other#0000000041',
            ],
            [
                'FOO#chk0#0000000039',
                'FOO#chk1#0000000042',
                'FOO#chk2#0000000043',
                'BAR#chk_some#0000000040',
                'BAR#chk_other#0000000041',
            ],
        ]
        zdc = zkdatacache.ZkDataCache(zkclient, '/zk/path', self.cachedir)
        zdc._cached = {
            'FOO': [
                zkdatacache.ZkCachedEntry(
                    fname='a#chk2', chksum='chk2', ctime='0'
                ),
                zkdatacache.ZkCachedEntry(
                    fname='a#chk1', chksum='chk1', ctime='0'
                ),
            ]
        }

        # Test "normal" pushing.
        zdc.push()

        zkclient.create.assert_called_with(
            '/zk/path/FOO#chk2' + '#',
            b'foo',
            makepath=True, sequence=True
        )
        self.assertEqual(
            treadmill.zkutils.ensure_deleted.call_args_list,
            [
                mock.call(zkclient, '/zk/path/FOO#chk1#0000000042'),
                mock.call(zkclient, '/zk/path/FOO#chk0#0000000039'),
            ]
        )

        treadmill.zkutils.ensure_deleted.reset_mock()
        zkclient.get_children.side_effect = None
        zkclient.create.reset_mock()

        # Test expunge pushing.
        zkclient.get_children.return_value = [
            'FOO#chk0#0000000039',
            'FOO#chk1#0000000042',
            'FOO#chk2#0000000043',
            'BAR#chk_some#0000000040',
            'BAR#chk_other#0000000041',
        ]
        zdc.refresh_zk(zkclient.get_children('/zk/path'))

        zdc.push(expunge=True)

        treadmill.zkutils.ensure_deleted.assert_has_calls(
            [
                mock.call(zkclient, '/zk/path/FOO#chk0#0000000039'),
                mock.call(zkclient, '/zk/path/BAR#chk_some#0000000040'),
                mock.call(zkclient, '/zk/path/BAR#chk_other#0000000041'),
                mock.call(zkclient, '/zk/path/FOO#chk1#0000000042'),
            ],
            any_order=True
        )
        self.assertEqual(
            treadmill.zkutils.ensure_deleted.call_count,
            4
        )

    @mock.patch('treadmill.zkutils.ZkClient.create', mock.Mock(set_spec=True))
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock(set_spec=True))
    @mock.patch('kazoo.client.KazooClient.get_children',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock(set_spec=True))
    def test_push_noop(self):
        """Test pushing data from the cache to Zookeeper.
        """
        # pylint: disable=protected-access

        zk_content = {
            'zk': {
                'path': {
                    'FOO#chk2#0000000042': b'foo',
                }
            }
        }
        self.make_mock_zk(zk_content)
        zkclient = treadmill.zkutils.ZkClient()
        zdc = zkdatacache.ZkDataCache(zkclient, '/zk/path', self.cachedir)
        zdc._cached = {
            'FOO': [
                zkdatacache.ZkCachedEntry(
                    fname='a#chk2', chksum='chk2', ctime='0'
                ),
                zkdatacache.ZkCachedEntry(
                    fname='a#chk1', chksum='chk1', ctime='0'
                ),
            ]
        }

        # Pushing when data already present should be a noop.
        zdc.push()

        zkclient.create.assert_not_called()
        treadmill.zkutils.ensure_deleted.assert_not_called()
        treadmill.zkutils.ensure_deleted.reset_mock()
        zkclient.create.reset_mock()


if __name__ == '__main__':
    unittest.main()
