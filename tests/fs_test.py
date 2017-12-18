"""Unit test for fs - Filesystem utilities.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import shutil
import sys
import tarfile
import tempfile
import unittest

import mock
import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

import treadmill
import treadmill.fs

if sys.platform.startswith('linux'):
    import treadmill.fs.linux


@unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
class FsLinuxTest(unittest.TestCase):
    """Tests for teadmill.fs.linux.
    """
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('treadmill.syscall.mount.unmount', mock.Mock(spec_set=True))
    def test_umount_filesystem(self):
        """Test umount call.
        """
        treadmill.fs.linux.umount_filesystem('/foo')

        treadmill.syscall.mount.unmount.assert_called_with(target='/foo')

    @mock.patch('treadmill.syscall.mount.mount', mock.Mock(spec_set=True))
    def test_mount_filesystem(self):
        """Test mounting a filesystem.
        """
        treadmill.fs.linux.mount_filesystem('/some/dev', '/some/mnt', 'type')

        treadmill.syscall.mount.mount.assert_called_with(
            source='/some/dev',
            target='/some/mnt',
            fs_type='type',
            mnt_flags=mock.ANY
        )

    @mock.patch('treadmill.syscall.mount.mount', mock.Mock(spec_set=True))
    def test_mount_bind_dir(self):
        """Tests bind mounting directory binding behavior
        """
        container_dir = os.path.join(self.root, 'container')
        os.makedirs(container_dir)
        foo_dir = os.path.join(self.root, 'foo')
        os.makedirs(foo_dir)

        treadmill.fs.linux.mount_bind(container_dir, foo_dir)

        container_foo_dir = os.path.join(container_dir, foo_dir[1:])
        treadmill.syscall.mount.mount.assert_has_calls(
            [
                mock.call(
                    source=foo_dir,
                    target=container_foo_dir,
                    fs_type=None,
                    mnt_flags=mock.ANY
                ),
                mock.call(
                    source=None,
                    target=container_foo_dir,
                    fs_type=None,
                    mnt_flags=mock.ANY
                ),
            ]
        )
        self.assertCountEqual(
            treadmill.syscall.mount.mount.call_args_list[0][1]['mnt_flags'],
            (
                treadmill.syscall.mount.MS_REC,
                treadmill.syscall.mount.MS_BIND,
            ),
            'Validate flags passed to first mount call'
        )
        self.assertCountEqual(
            treadmill.syscall.mount.mount.call_args_list[1][1]['mnt_flags'],
            (
                treadmill.syscall.mount.MS_BIND,
                treadmill.syscall.mount.MS_RDONLY,
                treadmill.syscall.mount.MS_REMOUNT,
            ),
            'Validate flags passed to second mount call'
        )
        self.assertEqual(
            treadmill.syscall.mount.mount.call_count, 2
        )
        self.assertTrue(
            os.path.isdir(container_foo_dir)
        )

    @mock.patch('treadmill.syscall.mount.mount', mock.Mock(spec_set=True))
    def test_mount_bind_dir_readwrite(self):
        """Tests bind mounting directory binding behavior (read/write)
        """
        container_dir = os.path.join(self.root, 'container')
        os.makedirs(container_dir)
        foo_dir = os.path.join(self.root, 'foo')
        os.makedirs(foo_dir)

        treadmill.fs.linux.mount_bind(container_dir, foo_dir, read_only=False)

        container_foo_dir = os.path.join(container_dir, foo_dir[1:])
        treadmill.syscall.mount.mount.assert_has_calls(
            [
                mock.call(
                    source=foo_dir,
                    target=container_foo_dir,
                    fs_type=None,
                    mnt_flags=mock.ANY
                ),
            ]
        )
        self.assertCountEqual(
            treadmill.syscall.mount.mount.call_args_list[0][1]['mnt_flags'],
            (
                treadmill.syscall.mount.MS_REC,
                treadmill.syscall.mount.MS_BIND,
            ),
            'Validate flags passed to first mount call'
        )
        self.assertEqual(
            treadmill.syscall.mount.mount.call_count, 1
        )
        self.assertTrue(
            os.path.isdir(container_foo_dir)
        )

    @mock.patch('treadmill.syscall.mount.mount', mock.Mock(spec_set=True))
    def test_mount_bind_file(self):
        """Verifies correct mount options for files vs dirs.
        """
        container_dir = os.path.join(self.root, 'container')
        os.makedirs(container_dir)
        foo_file = os.path.join(self.root, 'foo')
        with io.open(os.path.join(self.root, 'foo'), 'w'):
            pass

        treadmill.fs.linux.mount_bind(container_dir, foo_file)

        container_foo_file = os.path.join(container_dir, foo_file[1:])
        treadmill.syscall.mount.mount.assert_has_calls(
            [
                mock.call(
                    source=foo_file,
                    target=container_foo_file,
                    fs_type=None,
                    mnt_flags=mock.ANY
                ),
                mock.call(
                    source=None,
                    target=container_foo_file,
                    fs_type=None,
                    mnt_flags=mock.ANY
                ),
            ]
        )
        self.assertCountEqual(
            treadmill.syscall.mount.mount.call_args_list[0][1]['mnt_flags'],
            (
                treadmill.syscall.mount.MS_BIND,
            ),
            'Validate flags passed to first mount call'
        )
        self.assertCountEqual(
            treadmill.syscall.mount.mount.call_args_list[1][1]['mnt_flags'],
            (
                treadmill.syscall.mount.MS_BIND,
                treadmill.syscall.mount.MS_RDONLY,
                treadmill.syscall.mount.MS_REMOUNT,
            ),
            'Validate flags passed to second mount call'
        )
        self.assertEqual(
            treadmill.syscall.mount.mount.call_count, 2
        )
        self.assertTrue(
            os.path.isfile(container_foo_file)
        )

    @mock.patch('treadmill.syscall.mount.mount', mock.Mock(spec_set=True))
    def test_mount_bind_failures(self):
        """Tests mount_bind behavior with invalid input.
        """
        self.assertRaises(Exception,
                          treadmill.fs.linux.mount_bind,
                          'no_such_root', '/bin')
        self.assertRaises(Exception,
                          treadmill.fs.linux.mount_bind,
                          self.root, '/nosuchdir')
        self.assertRaises(Exception,
                          treadmill.fs.linux.mount_bind,
                          self.root, './relative')
        self.assertRaises(Exception,
                          treadmill.fs.linux.mount_bind,
                          self.root, 'relative')

    @mock.patch('treadmill.syscall.mount.mount', mock.Mock(spec_set=True))
    def test_mount_proc(self):
        """Test mounting of proc filesystem.
        """
        treadmill.fs.linux.mount_proc('/foo')

        treadmill.syscall.mount.mount.assert_called_with(
            source='proc',
            target='/foo/proc',
            fs_type='proc',
        )

    @mock.patch('treadmill.syscall.mount.mount', mock.Mock(spec_set=True))
    def test_mount_sysfs(self):
        """Test mounting of sysfs filesystem.
        """
        treadmill.fs.linux.mount_sysfs('/foo')

        treadmill.syscall.mount.mount.assert_called_with(
            source='sysfs',
            target='/foo/sys',
            fs_type='sysfs',
            mnt_flags=mock.ANY
        )
        self.assertCountEqual(
            treadmill.syscall.mount.mount.call_args_list[0][1]['mnt_flags'],
            (
                treadmill.syscall.mount.MS_RDONLY,
            ),
            'Validate flags passed to second mount call'
        )

    @mock.patch('treadmill.syscall.mount.mount', mock.Mock(spec_set=True))
    def test_mount_tmpfs(self):
        """Tests behavior of mount tmpfs.
        """
        treadmill.fs.linux.mount_tmpfs('/foo', '/tmp', size='4M')
        treadmill.syscall.mount.mount.assert_called_with(
            source='tmpfs',
            target='/foo/tmp',
            fs_type='tmpfs',
            mnt_flags=mock.ANY,
            mnt_opts={'size': '4M'}
        )
        self.assertCountEqual(
            treadmill.syscall.mount.mount.call_args_list[0][1]['mnt_flags'],
            (
                treadmill.syscall.mount.MS_NOATIME,
                treadmill.syscall.mount.MS_NODIRATIME,
            ),
            'Validate flags passed to second mount call'
        )
        treadmill.syscall.mount.mount.reset_mock()

        treadmill.fs.linux.mount_tmpfs('/foo', '/tmp2')

        treadmill.syscall.mount.mount.assert_called_with(
            source='tmpfs',
            target='/foo/tmp2',
            fs_type='tmpfs',
            mnt_flags=mock.ANY,
            mnt_opts={}
        )
        self.assertCountEqual(
            treadmill.syscall.mount.mount.call_args_list[0][1]['mnt_flags'],
            (
                treadmill.syscall.mount.MS_NOATIME,
                treadmill.syscall.mount.MS_NODIRATIME,
            ),
            'Validate flags passed to second mount call'
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock(spec_set=True))
    def test_blk_fs_create(self):
        """Test filesystem creation
        """
        treadmill.fs.linux.blk_fs_create('/dev/myapp')
        treadmill.subproc.check_call.assert_called_with(
            [
                'mke2fs',
                '-F',
                '-E', 'lazy_itable_init=1,nodiscard',
                '-O', 'uninit_bg',
                '/dev/myapp',
            ]
        )

    @mock.patch('treadmill.subproc.check_output',
                mock.Mock(spec_set=True,
                          return_value="""
Filesystem volume name:   /boot
Last mounted on:          <not available>
Filesystem UUID:          d19ecb0a-fa74-4be2-85f6-2e3a50901cd9
Filesystem magic number:  0xEF53
Filesystem revision #:    1 (dynamic)
Filesystem OS type:       Linux
Inode count:              65280
Block count:              1
Reserved block count:     2
Free blocks:              3
Block size:               1024
Default directory hash:   half_md4
Directory Hash Seed:      20c6af65-0208-4e71-99cb-d5532c02e3b8
"""))
    def test_blk_fs_info(self):
        """Test fs.read_filesystem_info()."""
        res = treadmill.fs.linux.blk_fs_info('/dev/treadmill/<uniq>')

        self.assertEqual(res['block count'], '1')
        self.assertEqual(res['reserved block count'], '2')
        self.assertEqual(res['free blocks'], '3')
        self.assertEqual(res['block size'], '1024')
        treadmill.subproc.check_output.reset_mock()

        treadmill.subproc.check_output.side_effect = (
            subprocess.CalledProcessError(1, 'command', 'some error')
        )

        self.assertEqual(
            treadmill.fs.linux.blk_fs_info('/dev/treadmill/<uniq>'),
            {}
        )

    @mock.patch('glob.glob',
                mock.Mock(spec_set=True,
                          return_value=('/sys/class/block/sda2/dev',
                                        '/sys/class/block/sda3/dev')))
    @mock.patch('io.open', mock.mock_open())
    def test_maj_min_to_blk(self):
        """Tests fs.maj_min_to_blk()"""
        io.open.return_value.read.side_effect = ['8:2\n', '8:3\n']

        self.assertEqual(
            treadmill.fs.linux.maj_min_to_blk(8, 3),
            '/dev/sda3'
        )
        io.open.reset_mock()

        io.open.return_value.read.side_effect = ['8:2\n', '8:3\n']

        self.assertIsNone(
            treadmill.fs.linux.maj_min_to_blk(1, 2)
        )


class FsTest(unittest.TestCase):
    """Tests for teadmill.fs."""

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    def test_rm_safe(self):
        """Test safe rm/unlink."""
        test_file = os.path.join(self.root, 'rmsafe_test')
        with io.open(test_file, 'w'):
            pass

        self.assertTrue(os.path.isfile(test_file))
        treadmill.fs.rm_safe(test_file)
        self.assertFalse(os.path.exists(test_file))
        treadmill.fs.rm_safe(test_file)
        self.assertFalse(os.path.exists(test_file))

    def test_rmtree_safe(self):
        """Test safe rmtree."""
        test_dir = os.path.join(self.root, 'rmsafe_test')
        os.mkdir(test_dir)

        self.assertTrue(os.path.isdir(test_dir))
        treadmill.fs.rmtree_safe(test_dir)
        self.assertFalse(os.path.exists(test_dir))
        treadmill.fs.rmtree_safe(test_dir)
        self.assertFalse(os.path.exists(test_dir))

    def test_tar_basic(self):
        """Tests the fs.tar function.
        """
        # Create directories and files to test tarring
        # /self.root/apps/testapp/tardir
        # /self.root/apps/testapp/tardir/file
        # /self.root/apps/testapp/tardir/subdir
        # /self.root/apps/testapp/tardir2
        # Archive:
        # /self.root/apps/testapp/tar.tar

        testapp_dir = os.path.join(self.root, 'testapp')
        tardir = os.path.join(testapp_dir, 'tardir')
        tardir2 = os.path.join(testapp_dir, 'tardir2')
        archive = os.path.join(testapp_dir, 'foo.tar')
        os.makedirs(testapp_dir)
        os.mkdir(tardir)
        os.mkdir(os.path.join(tardir, 'subdir'))
        os.mkdir(tardir2)
        with io.open(os.path.join(tardir, 'file'), 'w'):
            pass

        self.assertEqual(
            treadmill.fs.tar(archive, tardir).name,
            archive,
            'fs.tar runs successfully'
        )
        self.assertTrue(
            os.path.isfile(archive),
            'fs.tar creates a tarfile'
        )

        self.assertEqual(
            treadmill.fs.tar(archive, tardir2).name,
            archive,
            'fs.tar will succeed if tarfile already exists'
        )

        self.assertEqual(
            treadmill.fs.tar(archive, tardir, compression='gzip').name,
            '%s.gz' % archive,
            'fs.tar with gzip runs successfully'
        )
        self.assertTrue(
            os.path.isfile('%s.gz' % archive),
            'fs.tar creates a tar gzip file'
        )

    @mock.patch('tarfile.TarFile.add', mock.Mock())
    def test_tar_files(self):
        """Tests the glob/transform of files in fs.tar.
        """
        # Create directories and files to test tarring
        # /self.root/apps/testapp/tardir
        # /self.root/apps/testapp/tardir/file
        # /self.root/apps/testapp/tardir/subdir
        # /self.root/apps/testapp/tardir2
        # Archive:
        # /self.root/apps/testapp/tar.tar

        testapp_dir = os.path.join(self.root, 'testapp')
        tardir = os.path.join(testapp_dir, 'tardir')
        tardir2 = os.path.join(testapp_dir, 'tardir2')
        archive = os.path.join(testapp_dir, 'foo.tar')
        os.makedirs(testapp_dir)
        os.mkdir(tardir)
        os.mkdir(os.path.join(tardir, 'subdir'))
        os.mkdir(tardir2)
        with io.open(os.path.join(tardir, 'file'), 'w'):
            pass

        self.assertEqual(
            treadmill.fs.tar(
                archive, [tardir, tardir2],
                compression='gzip'
            ).name,
            '%s.gz' % archive,
            'fs.tar runs successfully'
        )
        tarfile.TarFile.add.assert_any_call(tardir, '/')
        tarfile.TarFile.add.assert_any_call(tardir2, '/')

    def test_tar_stream(self):
        """Test the stream mode of fs.tar
        """
        # Create directories and files to test tarring
        # /self.root/apps/testapp/tardir
        # /self.root/apps/testapp/tardir/file
        # /self.root/apps/testapp/tardir/subdir
        # /self.root/apps/testapp/tardir2

        testapp_dir = os.path.join(self.root, 'testapp')
        tardir = os.path.join(testapp_dir, 'tardir')
        tardir2 = os.path.join(testapp_dir, 'tardir2')
        os.makedirs(testapp_dir)
        os.mkdir(tardir)
        os.mkdir(os.path.join(tardir, 'subdir'))
        os.mkdir(tardir2)
        with io.open(os.path.join(tardir, 'file'), 'w'):
            pass
        with io.open(os.path.join(tardir2, 'file2'), 'w+'):
            pass

        fileobj = tempfile.TemporaryFile()
        treadmill.fs.tar(target=fileobj, sources=[tardir, tardir2],
                         compression='gzip')

        # seek fileobj and check content
        fileobj.seek(0)
        tarfileobj = tarfile.open(mode='r:gz', fileobj=fileobj)
        names = tarfileobj.getnames()
        self.assertTrue(
            'subdir' in names and 'file' in names and 'file2' in names
        )


if __name__ == '__main__':
    unittest.main()
