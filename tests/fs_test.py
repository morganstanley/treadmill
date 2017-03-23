"""
Unit test for fs - configuring unshared chroot.
"""

import collections
import os
import shutil
import stat
import tarfile
import tempfile
import unittest

import mock

import treadmill
from treadmill import fs


_CLONE_NEWNS = treadmill.syscall.unshare.CLONE_NEWNS


# Pylint complains about long names for test functions.
# pylint: disable=C0103
class FsTest(unittest.TestCase):
    """Tests for teadmill.fs."""

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('os.path.isdir', mock.Mock(return_value=False))
    @mock.patch('treadmill.syscall.unshare.unshare', mock.Mock(return_value=0))
    @mock.patch('os.makedirs', mock.Mock(return_value=0))
    def test_chroot_init_ok(self):
        """Mock test, verifies root directory created and unshare called."""
        fs.chroot_init('/var/bla')
        os.makedirs.assert_called_with('/var/bla', mode=0o777)
        treadmill.syscall.unshare.unshare.assert_called_with(_CLONE_NEWNS)

    @mock.patch('os.path.exists', mock.Mock(return_value=True))
    @mock.patch('treadmill.syscall.unshare.unshare', mock.Mock(return_value=0))
    @mock.patch('os.makedirs', mock.Mock(return_value=0))
    def test_chroot_init_empty_existing(self):
        """Checks that chroot can be done over existing empty dir."""
        fs.chroot_init('/var/bla')
        os.makedirs.assert_called_with('/var/bla', mode=0o777)
        treadmill.syscall.unshare.unshare.assert_called_with(_CLONE_NEWNS)

    @mock.patch('os.path.exists', mock.Mock(return_value=False))
    @mock.patch('treadmill.syscall.unshare.unshare', mock.Mock(return_value=0))
    @mock.patch('os.makedirs', mock.Mock(return_value=0))
    def test_chroot_init_relative_path(self):
        """Checks chroot_init fails with relative path."""
        self.assertRaises(Exception, fs.chroot_init, '../bla')
        self.assertFalse(treadmill.syscall.unshare.unshare.called)
        self.assertFalse(os.makedirs.called)

    @mock.patch('os.chdir', mock.Mock(return_value=0))
    @mock.patch('os.chroot', mock.Mock(return_value=0))
    def test_chroot_finalize(self):
        """Checks final step is calling os.chroot."""
        fs.chroot_finalize('/bla/foo')

        os.chroot.assert_called_with('/bla/foo')
        os.chdir.assert_called_with('/')

    @mock.patch('os.chroot', mock.Mock(side_effect=OSError))
    def test_chroot_finalize_chroot_failure(self):
        """Ensures failure if os.chroot returns non zero rc."""
        self.assertRaises(OSError, fs.chroot_finalize, '/bla/foo')
        os.chroot.assert_called_with('/bla/foo')

    def test_chroot_finalize_invalid_path(self):
        """chroot_finalize must use absolute path."""
        self.assertRaises(Exception, fs.chroot_finalize, 'bla/foo')
        self.assertRaises(Exception, fs.chroot_finalize, './bla/foo')

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
        with open(foo_file, 'w'):
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

    @mock.patch('pwd.getpwnam', mock.Mock(
        return_value=collections.namedtuple('pwnam', 'pw_uid pw_gid')(42, 42)
    ))
    @mock.patch('os.chown', mock.Mock())
    @mock.patch('treadmill.fs.chroot_init', mock.Mock())
    @mock.patch('treadmill.fs.mount_bind', mock.Mock())
    @mock.patch('treadmill.fs.mount_tmpfs', mock.Mock())
    def test_make_rootfs(self):
        """Validates directory layout in chrooted environment."""
        fs.make_rootfs(self.root, "someproid")

        def isdir(path):
            """Checks directory presence in chrooted environment."""
            return os.path.isdir(os.path.join(self.root, path))

        def issticky(path):
            """Checks directory mode in chrooted environment."""
            statinfo = os.stat(os.path.join(self.root, path))
            return statinfo.st_mode & stat.S_ISVTX

        self.assertTrue(isdir('tmp'))
        self.assertTrue(isdir('opt'))
        # self.assertTrue(isdir('u'))
        # self.assertTrue(isdir('var/hostlinks'))
        # self.assertTrue(isdir('var/account'))
        # self.assertTrue(isdir('var/empty'))
        # self.assertTrue(isdir('var/lock'))
        # self.assertTrue(isdir('var/lock/subsys'))
        # self.assertTrue(isdir('var/run'))
        self.assertTrue(isdir('var/spool/keytabs'))
        self.assertTrue(isdir('var/spool/tickets'))
        self.assertTrue(isdir('var/spool/tokens'))
        self.assertTrue(isdir('var/tmp'))
        self.assertTrue(isdir('var/tmp/cores'))
        self.assertTrue(isdir('home'))

        self.assertTrue(issticky('tmp'))
        self.assertTrue(issticky('opt'))
        # self.assertTrue(issticky('u'))
        # self.assertTrue(issticky('var/hostlinks'))
        self.assertTrue(issticky('var/tmp'))
        self.assertTrue(issticky('var/tmp/cores'))
        self.assertTrue(issticky('var/spool/tickets'))

        treadmill.fs.mount_tmpfs.assert_has_calls([
            mock.call(mock.ANY, '/var/spool/tickets', mock.ANY),
            mock.call(mock.ANY, '/var/spool/keytabs', mock.ANY)
        ])

        treadmill.fs.mount_bind.assert_has_calls([
            mock.call(mock.ANY, '/bin')
        ])

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
        open(test_file, 'w+').close()

        self.assertTrue(os.path.isfile(test_file))
        fs.rm_safe(test_file)
        self.assertFalse(os.path.exists(test_file))
        fs.rm_safe(test_file)
        self.assertFalse(os.path.exists(test_file))

    @mock.patch('os.path.exists', mock.Mock())
    @mock.patch('treadmill.fs.mount_bind', mock.Mock())
    def ytest_make_nfs(self):
        """Test mount_binding /v based on environment."""
        os.path.exists.return_value = False
        fs.make_nfs('/nfs_base', 'dev', self.root)
        treadmill.fs.mount_bind.assert_called_with(self.root, '/v', '/tmp_ns')
        treadmill.fs.mount_bind.clear()

        fs.make_nfs('/nfs_base', 'prod', self.root)
        treadmill.fs.mount_bind.assert_called_with(self.root, '/v', '/tmp_ns')
        treadmill.fs.mount_bind.clear()

        os.path.exists.return_value = True
        fs.make_nfs('/nfs_base', 'dev', self.root)
        treadmill.fs.mount_bind.assert_called_with(self.root, '/v',
                                                   '/nfs_base/dev')
        treadmill.fs.mount_bind.clear()

        fs.make_nfs('/nfs_base', 'prod', self.root)
        treadmill.fs.mount_bind.assert_called_with(self.root, '/v',
                                                   '/nfs_base/prod')
        treadmill.fs.mount_bind.clear()

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
        with open(os.path.join(tardir, 'file'), 'w+'):
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
        with open(os.path.join(tardir, 'file'), 'w+'):
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
        with open(os.path.join(tardir, 'file'), 'w+'):
            pass
        with open(os.path.join(tardir2, 'file2'), 'w+'):
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


if __name__ == '__main__':
    unittest.main()
