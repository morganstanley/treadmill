"""Unit test for fs - Filesystem utilities.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import shutil
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
from treadmill import fs


# Pylint complains about long names for test functions.
# pylint: disable=C0103
class FsTest(unittest.TestCase):
    """Tests for teadmill.fs."""

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_mount_bind_dir(self):
        """Tests fs.mount_bind directory binding behavior"""
        # test binding directory in /
        container_dir = os.path.join(self.root, 'container')
        os.makedirs(container_dir)

        foo_dir = os.path.join(self.root, 'foo')
        os.makedirs(foo_dir)
        fs.mount_bind(container_dir, foo_dir)
        treadmill.subproc.check_call.assert_called_with(
            [
                'mount',
                '-n',
                '--rbind',
                foo_dir,
                os.path.join(container_dir, foo_dir[1:]),
            ]
        )
        self.assertTrue(
            os.path.isdir(os.path.join(container_dir, foo_dir[1:]))
        )
        treadmill.subproc.check_call.reset_mock()
        self.assertTrue(
            os.path.isdir(
                os.path.join(container_dir, foo_dir[1:])
            )
        )

        # test binding directory with subdirs
        bar_dir = os.path.join(self.root, 'bar')
        os.makedirs(os.path.join(bar_dir, 'baz'))
        fs.mount_bind(container_dir, bar_dir)
        treadmill.subproc.check_call.assert_called_with(
            [
                'mount',
                '-n',
                '--rbind',
                bar_dir,
                os.path.join(container_dir, bar_dir[1:])
            ]
        )
        self.assertTrue(
            os.path.isdir(os.path.join(container_dir, bar_dir[1:]))
        )
        treadmill.subproc.check_call.reset_mock()

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_mount_bind_file(self):
        """Verifies correct mount options for files vs dirs."""
        container_dir = os.path.join(self.root, 'container')
        os.makedirs(container_dir)

        # test binding a file
        foo_file = os.path.join(self.root, 'foo')
        with io.open(os.path.join(self.root, 'foo'), 'w'):
            pass
        fs.mount_bind(container_dir, foo_file)
        treadmill.subproc.check_call.assert_called_with(
            [
                'mount',
                '-n',
                '--bind',
                foo_file,
                os.path.join(container_dir, foo_file[1:])
            ]
        )
        self.assertTrue(
            os.path.isfile(os.path.join(container_dir, foo_file[1:]))
        )
        treadmill.subproc.check_call.reset_mock()

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_mount_bind_failures(self):
        """Tests mount_bind behavior with invalid input."""
        self.assertRaises(Exception, fs.mount_bind, 'no_such_root', '/bin')
        self.assertRaises(Exception, fs.mount_bind, self.root, '/nosuchdir')
        self.assertRaises(Exception, fs.mount_bind, self.root, './relative')
        self.assertRaises(Exception, fs.mount_bind, self.root, 'relative')

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_mount_tmpfs(self):
        """Tests behavior of mount_tmpfs."""
        # Using absolute path to mount dir inside chroot
        treadmill.fs.mount_tmpfs('/a/b', '/var/spool/tickets', '4M')
        treadmill.subproc.check_call.assert_called_with(
            ['mount', '-n', '-o', 'size=4M', '-t', 'tmpfs', 'tmpfs',
             '/a/b/var/spool/tickets'])

        treadmill.subproc.check_call.reset()
        # Using relative path to mount dir
        treadmill.fs.mount_tmpfs('/a/b', 'var/spool/tickets', '2M')
        treadmill.subproc.check_call.assert_called_with(
            ['mount', '-n', '-o', 'size=2M', '-t', 'tmpfs', 'tmpfs',
             '/a/b/var/spool/tickets'])

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_create_filesystem(self):
        """Test loopback filesystem creation"""
        treadmill.fs.create_filesystem('/dev/myapp')
        treadmill.subproc.check_call.assert_called_with(
            [
                'mke2fs',
                '-F',
                '-E', 'lazy_itable_init=1,nodiscard',
                '-O', 'uninit_bg',
                '/dev/myapp',
            ]
        )

    @mock.patch('treadmill.utils.rootdir', mock.Mock(return_value='tm_root'))
    def test_archive_filesystem_empty(self):
        """Test filesystem archiving"""
        rootdir = os.path.join(self.root, 'apps', 'myapp.0', 'root')
        fs.mkdir_safe(rootdir)
        archive = os.path.join(self.root, 'arch.tar.bz2')

        self.assertTrue(
            treadmill.fs.archive_filesystem('/dev/myapp', rootdir, archive, [])
        )

    @mock.patch('treadmill.utils.rootdir', mock.Mock(return_value='tm_root'))
    @mock.patch('treadmill.subproc.call', mock.Mock(return_value=0))
    def test_archive_filesystem(self):
        """Test filesystem archiving"""
        rootdir = os.path.join(self.root, 'apps', 'myapp.0', 'root')
        fs.mkdir_safe(rootdir)
        archive = os.path.join(self.root, 'arch.tar.bz2')

        treadmill.fs.archive_filesystem(
            '/dev/myapp', rootdir, archive,
            ['/var/tmp/archive1', '/var/tmp/archive2'])

        treadmill.subproc.call.assert_called_with(
            ['unshare', '--mount',
             'tm_root/sbin/archive_container.sh',
             '/dev/myapp', rootdir, archive,
             'var/tmp/archive1', 'var/tmp/archive2']
        )

    def test_rm_safe(self):
        """Test safe rm/unlink."""
        test_file = os.path.join(self.root, 'rmsafe_test')
        with io.open(test_file, 'w'):
            pass

        self.assertTrue(os.path.isfile(test_file))
        fs.rm_safe(test_file)
        self.assertFalse(os.path.exists(test_file))
        fs.rm_safe(test_file)
        self.assertFalse(os.path.exists(test_file))

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
            fs.tar(archive, tardir).name,
            archive,
            'fs.tar runs successfully'
        )
        self.assertTrue(
            os.path.isfile(archive),
            'fs.tar creates a tarfile'
        )

        self.assertEqual(
            fs.tar(archive, tardir2).name,
            archive,
            'fs.tar will succeed if tarfile already exists'
        )

        self.assertEqual(
            fs.tar(archive, tardir, compression='gzip').name,
            "%s.gz" % archive,
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
            fs.tar(archive, [tardir, tardir2], compression='gzip').name,
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
        fs.tar(target=fileobj, sources=[tardir, tardir2],
               compression='gzip')

        # seek fileobj and check content
        fileobj.seek(0)
        tarfileobj = tarfile.open(mode='r:gz', fileobj=fileobj)
        names = tarfileobj.getnames()
        self.assertTrue(
            'subdir' in names and 'file' in names and 'file2' in names
        )

    @mock.patch('treadmill.subproc.check_output',
                mock.Mock(return_value="""
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
    def test_read_filesystem_info(self):
        """Test fs.read_filesystem_info()."""
        res = fs.read_filesystem_info('/dev/treadmill/<uniq>')

        self.assertEqual(res['block count'], '1')
        self.assertEqual(res['reserved block count'], '2')
        self.assertEqual(res['free blocks'], '3')
        self.assertEqual(res['block size'], '1024')

        with mock.patch('treadmill.subproc.check_output',
                        side_effect=subprocess.CalledProcessError(
                            1, 'command', 'some error')):

            self.assertEqual(fs.read_filesystem_info('/dev/treadmill/<uniq>'),
                             {})

    @mock.patch('io.open', mock.mock_open())
    @mock.patch('glob.glob',
                mock.Mock(return_value=('/sys/class/block/sda2/dev',
                                        '/sys/class/block/sda3/dev')))
    def test_maj_min_to_blk(self):
        """Tests fs.maj_min_to_blk()"""
        io.open.return_value.read.side_effect = ['8:2\n', '8:3\n']

        self.assertEqual(
            fs.maj_min_to_blk(8, 3),
            '/dev/sda3'
        )

        io.open.reset_mock()
        io.open.return_value.read.side_effect = ['8:2\n', '8:3\n']

        self.assertIsNone(fs.maj_min_to_blk(-1, -2))


if __name__ == '__main__':
    unittest.main()
