"""Kernel watchdog system.
"""

import codecs
import io
import logging
import os

import jinja2
import pkg_resources

from treadmill import fs
from treadmill import subproc

_LOGGER = logging.getLogger(__name__)
_JINJA2_ENV = jinja2.Environment(loader=jinja2.PackageLoader(__name__))


class KernelWatchdog(object):
    """Kernel watchdog."""

    def __init__(self, root, reboot_script):
        """
        :param root: watchdog base directory
        :param reboot_script: reboot script
        """
        self.root = root
        self.reboot_script = reboot_script
        self.pid_file = '/var/run/watchdog.pid'
        self.config_file = os.path.join(self.root, 'watchdog.conf')
        self.script_directory = os.path.join(self.root, 'script')
        self.test_directory = os.path.join(self.root, 'watchdog.d')
        self.tests = {}
        utf8_reader = codecs.getreader('utf8')
        test_names = pkg_resources.resource_listdir(
            'treadmill', '/etc/kernel_watchdog_tests'
        )
        for test_name in test_names:
            self.tests[test_name] = utf8_reader(
                pkg_resources.resource_stream(
                    'treadmill',
                    '/etc/kernel_watchdog_tests/{}'.format(test_name)
                )
            ).read()
        self.start_command = ['watchdog', '-c', self.config_file, '-b']

    def start(self):
        """Start watchdog."""
        _LOGGER.info('Setting up kernel watchdog at %s', self.root)

        # set up clean base directory
        fs.rmtree_safe(self.root)
        fs.mkdir_safe(self.root)
        fs.mkdir_safe(self.script_directory)
        fs.mkdir_safe(self.test_directory)

        # set up configuration
        config = _JINJA2_ENV.get_template(
            'kernel-watchdog-conf'
        ).render(
            test_directory=self.test_directory
        )
        with io.open(self.config_file, 'w') as fd:
            fd.write(config)

        # set up custom tests
        for name in self.tests:
            test_script = os.path.join(self.script_directory, name)
            # test script
            with io.open(test_script, 'w') as fd:
                fd.write(self.tests[name])
                os.fchmod(fd.fileno(), 0o755)
            # custom test
            custom_test = _JINJA2_ENV.get_template(
                'kernel-watchdog-test'
            ).render(
                name=name,
                command=test_script,
                reboot=self.reboot_script
            )
            with io.open(
                os.path.join(self.test_directory, name), 'w'
            ) as fd:
                fd.write(custom_test)
                os.fchmod(fd.fileno(), 0o755)

        _LOGGER.info('Starting up kernel watchdog')
        subproc.exec_fghack(self.start_command)
