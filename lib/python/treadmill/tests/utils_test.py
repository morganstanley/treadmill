"""This contains the unit tests for treadmill.utils.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import io
import os
import shutil
import signal
import stat  # pylint: disable=wrong-import-order
import sys
import tempfile
import time
import unittest

# Disable W0402: string deprecated
# pylint: disable=W0402
import string
import ipaddress

import mock
import six

from treadmill import exc
from treadmill import utils
from treadmill import templates
from treadmill import yamlwrapper as yaml

if sys.platform.startswith('linux'):
    import resource	 # pylint: disable=import-error


class UtilsTest(unittest.TestCase):
    """This contains the treadmill.utils tests."""

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    @mock.patch('treadmill.subproc.get_aliases', mock.Mock(return_value={}))
    def test_create_script_linux(self):
        """this tests the create_script function.

        the function creates executable scripts from templates that exist
        in the template directory.
        """
        script_file = os.path.join(self.root, 'script')
        # Function we are testing
        templates.create_script(
            script_file,
            's6.run',
            user='testproid',
            home='home',
            shell='shell',
            _alias={
                's6_setuidgid': '/test/s6-setuidgid',
            }
        )

        # Read the output from the mock filesystem
        with io.open(script_file) as script:
            data = script.read()

        # Validate that data is what it should be
        self.assertTrue(data.index(
            '/test/s6-setuidgid testproid') > 0)

        # Validate that the file is +x
        self.assertEqual(utils.os.stat(script_file).st_mode, 33261)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    @mock.patch('treadmill.subproc.get_aliases', mock.Mock(return_value={}))
    def test_create_script_perms_linux(self):
        """this tests the create_script function (permissions).
        """
        script_file = os.path.join(self.root, 'script')
        # Test non-default mode (+x)
        mode = (stat.S_IRUSR |
                stat.S_IRGRP |
                stat.S_IROTH)

        templates.create_script(
            script_file,
            's6.run',
            mode=mode,
            user='testproid',
            home='home',
            shell='shell',
            _alias={
                's6_setuidgid': '/test/s6-setuidgid',
            }
        )

        self.assertEqual(utils.os.stat(script_file).st_mode, 33060)

    def test_base_n(self):
        """Test to/from_base_n conversions."""
        alphabet = (string.digits +
                    string.ascii_lowercase +
                    string.ascii_uppercase)

        for base in [2, 10, 16, 36, 62]:
            for num in [0, 10, 2313, 23134223879243284]:
                n_num = utils.to_base_n(num, base=base, alphabet=alphabet)
                _num = utils.from_base_n(n_num, base=base, alphabet=alphabet)
                self.assertTrue(num == _num)

        self.assertEqual(utils.to_base_n(15, base=16), 'f')
        self.assertEqual(utils.to_base_n(10, base=2), '1010')

        self.assertEqual(
            utils.from_base_n('101', base=2),
            int('101', base=2),
        )
        self.assertEqual(
            utils.from_base_n('deadbeef', base=16),
            int('deadbeef', base=16)
        )

    def test_ip2int(self):
        """Tests IP string to int representation conversion."""
        self.assertEqual(0x40E9BB63, utils.ip2int('64.233.187.99'))

        ip = utils.ip2int('192.168.100.1')
        self.assertEqual('192.168.100.2', utils.int2ip(ip + 1))
        self.assertEqual('192.168.100.0', utils.int2ip(ip - 1))

        ip = utils.ip2int('192.168.100.255')
        self.assertEqual('192.168.101.0', utils.int2ip(ip + 1))

        ip = utils.ip2int('192.168.100.0')
        self.assertEqual('192.168.99.255', utils.int2ip(ip - 1))

    def test_to_obj(self):
        """Tests dict to namedtuple conversion."""
        obj = utils.to_obj({'a': 1, 'b': 2, 'c': 3}, 'foo')
        self.assertEqual(1, obj.a)
        self.assertEqual(2, obj.b)
        self.assertEqual(3, obj.c)

        obj = utils.to_obj({'a': 1, 'b': [1, 2, 3], 'c': 3}, 'foo')
        self.assertEqual(1, obj.a)
        self.assertEqual([1, 2, 3], obj.b)
        self.assertEqual(3, obj.c)

        obj = utils.to_obj({'a': 1, 'b': {'d': 5}, 'c': 3}, 'foo')
        self.assertEqual(1, obj.a)
        self.assertEqual(5, obj.b.d)
        self.assertEqual(3, obj.c)

        obj = utils.to_obj({'a': [1, {'d': 5}, 3], 'b': 33}, 'foo')
        self.assertEqual(1, obj.a[0])
        self.assertEqual(5, obj.a[1].d)
        self.assertEqual(3, obj.a[2])
        self.assertEqual(33, obj.b)

    def test_kilobytes(self):
        """Test memory/disk size string conversion."""
        self.assertEqual(10, utils.kilobytes('10K'))
        self.assertEqual(10, utils.kilobytes('10k'))
        self.assertRaises(Exception, utils.kilobytes, '10')

        self.assertEqual(10 * 1024, utils.kilobytes('10M'))
        self.assertEqual(10 * 1024, utils.kilobytes('10m'))

        self.assertEqual(10 * 1024 * 1024, utils.kilobytes('10G'))
        self.assertEqual(10 * 1024 * 1024, utils.kilobytes('10g'))

    def test_size_to_bytes(self):
        """Test conversion of units to bytes."""
        self.assertEqual(10, utils.size_to_bytes(10))
        self.assertEqual(-10, utils.size_to_bytes(-10))
        self.assertEqual(10, utils.size_to_bytes('10'))
        self.assertEqual(-10, utils.size_to_bytes('-10'))
        self.assertEqual(10 * 1024, utils.size_to_bytes('10K'))
        self.assertEqual(-10 * 1024, utils.size_to_bytes('-10K'))
        self.assertEqual(-10 * 1024 * 1024, utils.size_to_bytes('-10M'))

    def test_cpuunits(self):
        """Test conversion of cpu string to bmips."""
        self.assertEqual(10, utils.cpu_units('10%'))
        self.assertEqual(10, utils.cpu_units('10'))

    def test_validate(self):
        """Tests dictionary validation."""
        schema = [
            ('required', True, str),
            ('optional', False, str),
        ]

        struct = {'required': 'foo'}
        utils.validate(struct, schema)
        self.assertNotIn('optional', struct)

        struct = {'required': 'foo', 'optional': 'xxx'}
        utils.validate(struct, schema)

        struct = {'required': 'foo', 'optional': 1234}
        self.assertRaises(Exception, utils.validate,
                          struct, schema)

        schema = [
            ('required', True, list),
            ('optional', False, list),
        ]

        struct = {'required': ['foo']}
        utils.validate(struct, schema)

        struct = {'required': 'foo'}
        self.assertRaises(Exception, utils.validate,
                          struct, schema)

    def test_to_seconds(self):
        """Tests time interval to seconds conversion."""
        self.assertEqual(0, utils.to_seconds('0s'))
        self.assertEqual(3, utils.to_seconds('3s'))
        self.assertEqual(180, utils.to_seconds('3m'))
        self.assertEqual(7200, utils.to_seconds('2h'))
        self.assertEqual(259200, utils.to_seconds('3d'))

    def test_find_in_path(self):
        """Tests finding program in system path."""
        # pylint: disable=protected-access

        temp_dir = self.root
        saved_path = os.environ['PATH']
        # xxxx is not in path
        self.assertEqual('xxxx', utils.find_in_path('xxxx'))

        os.environ['PATH'] = os.environ['PATH'] + os.pathsep + temp_dir

        io.open(os.path.join(temp_dir, 'xxxx'), 'w').close()

        if os.name == 'posix':
            # xxxx is in path, but not executable.
            self.assertEqual('xxxx', utils.find_in_path('xxxx'))
            os.chmod(os.path.join(temp_dir, 'xxxx'), int(templates._EXEC_MODE))

        self.assertEqual(
            os.path.join(temp_dir, 'xxxx'),
            utils.find_in_path('xxxx')
        )

        os.environ['PATH'] = saved_path

    def test_humanreadable(self):
        """Tests conversion of values into human readable format."""
        self.assertEqual('1.0M', utils.bytes_to_readable(1024, 'K'))
        self.assertEqual('1.0G', utils.bytes_to_readable(1024, 'M'))
        self.assertEqual(
            '2.5T',
            utils.bytes_to_readable(1024 * 1024 * 2.5, 'M')
        )
        self.assertEqual('1.0K', utils.bytes_to_readable(1024, 'B'))

    def test_tail(self):
        """Tests utils.tail."""
        filed, filepath = tempfile.mkstemp()
        with os.fdopen(filed, 'w') as f:
            for i in six.moves.range(0, 5):
                f.write('%d\n' % i)

        with io.open(filepath) as f:
            lines = utils.tail_stream(f)
            self.assertEqual(['0\n', '1\n', '2\n', '3\n', '4\n'], lines)
        os.unlink(filepath)

        filed, filepath = tempfile.mkstemp()
        with os.fdopen(filed, 'w') as f:
            for i in six.moves.range(0, 10000):
                f.write('%d\n' % i)
        with io.open(filepath) as f:
            lines = utils.tail_stream(f, 5)
            self.assertEqual(
                ['9995\n', '9996\n', '9997\n', '9998\n', '9999\n'],
                lines
            )

        # Test utils.tail given the file name.
        lines = utils.tail(filepath, 5)
        self.assertEqual(
            ['9995\n', '9996\n', '9997\n', '9998\n', '9999\n'],
            lines
        )
        os.unlink(filepath)

        self.assertEqual([], utils.tail('/no/such/thing'))

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    @mock.patch('os.write', mock.Mock())
    @mock.patch('os.close', mock.Mock())
    def test_report_ready(self):
        """Tests reporting service readyness."""

        cwd = os.getcwd()
        tmpdir = self.root
        os.chdir(tmpdir)

        utils.report_ready()
        self.assertFalse(os.write.called)
        self.assertFalse(os.close.called)

        utils.report_ready(100)
        os.write.assert_called_with(100, mock.ANY)
        os.close.assert_called_with(100)

        os.write.reset()
        os.close.reset()
        with io.open('notification-fd', 'w') as f:
            f.write('300')
        utils.report_ready()
        os.write.assert_called_with(300, mock.ANY)
        os.close.assert_called_with(300)

        os.write.reset()
        os.close.reset()
        with io.open('notification-fd', 'w') as f:
            f.write('300\n')
        utils.report_ready()
        os.write.assert_called_with(300, mock.ANY)
        os.close.assert_called_with(300)

        os.chdir(cwd)

    def test_cidr_range(self):
        """Test cidr range"""
        result1 = utils.cidr_range(174472034, 174472038)
        result2 = utils.cidr_range('10.102.59.98', '10.102.59.102')
        expected = [
            ipaddress.IPv4Network(u'10.102.59.98/31'),
            ipaddress.IPv4Network(u'10.102.59.100/31'),
            ipaddress.IPv4Network(u'10.102.59.102/32')
        ]
        self.assertEqual(result1, expected)
        self.assertEqual(result2, expected)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    def test_signal_flag(self):
        """Tests signal flag."""
        signalled = utils.make_signal_flag(signal.SIGHUP, signal.SIGTERM)
        self.assertFalse(signalled)

        os.kill(os.getpid(), signal.SIGHUP)
        time.sleep(0.1)
        self.assertTrue(signalled)

        signalled.clear()
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(0.1)
        self.assertTrue(signalled)

    def test_to_yaml(self):
        """Tests conversion of dict to yaml representation."""
        obj = {
            'xxx': u'abcd'
        }

        self.assertEqual(yaml.dump(obj), u'{xxx: abcd}\n')

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    @mock.patch('os.closerange', mock.Mock(spec_set=True))
    @mock.patch('os.listdir', mock.Mock(spec_set=True))
    @mock.patch('resource.getrlimit', mock.Mock(spec_set=True))
    def test_closefrom(self):
        """Tests sane execvp wrapper.
        """
        os.listdir.return_value = ['0', '1', '6', '7']

        utils.closefrom(4)

        os.closerange.assert_called_with(4, 7)
        resource.getrlimit.assert_not_called()
        os.closerange.reset_mock()
        resource.getrlimit.reset_mock()

        os.listdir.side_effect = OSError('No such file or dir', errno.ENOENT)
        resource.getrlimit.return_value = (100, 1024**2)

        utils.closefrom(4)

        os.closerange.assert_called_with(4, 1024**2)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    @mock.patch('signal.signal', mock.Mock(spec_set=True))
    @mock.patch('os.execvp', mock.Mock(spec_set=True))
    @mock.patch('treadmill.utils.closefrom', mock.Mock(spec_set=True))
    def test_sane_execvp(self):
        """Tests sane execvp wrapper.
        """
        # do not complain about accessing protected member _SIGNALS
        # pylint: disable=W0212

        utils.sane_execvp('/bin/sleep', ['sleep', '30'])

        if six.PY2:
            utils.closefrom.assert_called_with(3)
        signal.signal.assert_has_calls(
            [
                mock.call(i, signal.SIG_DFL)
                for i in utils._SIGNALS
            ]
        )
        os.execvp.assert_called_with('/bin/sleep', ['sleep', '30'])

    @mock.patch('treadmill.utils.sys_exit', mock.Mock())
    def test_decorator_tm_exc(self):
        """Test the `exit_on_unhandled` decorator on `TreadmillError`."""
        @utils.exit_on_unhandled
        def test_fun():
            """raise exc.TreadmillError('test')."""
            raise exc.TreadmillError('test')

        test_fun()

        utils.sys_exit.assert_called_with(-1)

    @mock.patch('treadmill.utils.sys_exit', mock.Mock())
    def test_decorator_py_exc(self):
        """Test the `exit_on_unhandled` decorator on Python `Exception`."""
        @utils.exit_on_unhandled
        def test_fun():
            """raise Exception('test')."""
            raise Exception('test')

        test_fun()

        utils.sys_exit.assert_called_with(-1)

    def test_reboot_schedule(self):
        """Test reboot schedule parsing."""
        self.assertEqual(
            utils.reboot_schedule('sun'),
            {6: (23, 59, 59)}
        )
        self.assertEqual(
            utils.reboot_schedule('sun/2:00:00'),
            {6: (2, 0, 0)}
        )
        self.assertEqual(
            utils.reboot_schedule('sun/2:05:00'),
            {6: (2, 5, 0)}
        )
        self.assertEqual(
            utils.reboot_schedule('sat,sun/02:00:00'),
            {5: (23, 59, 59),
             6: (2, 0, 0)}
        )


if __name__ == '__main__':
    unittest.main()
