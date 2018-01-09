"""Treadmill cell checkout.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import datetime
import io
import logging
import multiprocessing
import os
import random
import time
import traceback
import socket
import unittest

import click
import flask
import HtmlTestRunner

from treadmill import cli
from treadmill import context
from treadmill import fs
from treadmill import utils
from treadmill import sysinfo
from treadmill import plugin_manager


_LOGGER = logging.getLogger(__name__)


def _cleanup(outdir, age):
    """Cleanup old report files."""
    _LOGGER.info('Running cleanup.')
    age_sec = utils.to_seconds(age)

    now = time.time()
    for filename in os.listdir(outdir):
        fullpath = os.path.join(outdir, filename)
        created_at = os.stat(fullpath).st_ctime
        if created_at < now - age_sec:
            _LOGGER.info('Removing old file: %s', fullpath)
            fs.rm_safe(fullpath)


def init():
    """Return top level command handler."""

    @click.group(cls=cli.make_commands('treadmill.cli.admin.checkout',
                                       chain=True,
                                       invoke_without_command=True))
    @click.option('--outdir', help='Output directory.',
                  required=True, type=click.Path(exists=True))
    @click.option('--interval', help='Interval between tests.',
                  required=False, type=int, default=60 * 5)
    @click.option('--randomize',
                  help='Optional random interval between tests.',
                  required=False, type=int, default=60 * 5)
    @click.option('--age',
                  help='Max report age to keep.',
                  default='1d')
    @click.option('--processor',
                  help='Result processing plugin.',
                  type=cli.LIST)
    def run(outdir, interval, randomize, age, processor):
        """Test treadmill infrastructure."""
        del outdir
        del interval
        del randomize
        del age
        del processor

    @run.resultcallback()
    def run_tests(tests, outdir, interval, randomize, age, processor):
        """Test treadmill infrastructure."""

        _LOGGER.info('Starting tests: %s', outdir)
        fs.mkdir_safe(outdir)

        while True:

            report_name = '%s.html' % datetime.datetime.isoformat(
                datetime.datetime.now()
            )
            report_file = os.path.join(outdir, report_name)
            _LOGGER.info('Running checkout suite: %s', report_file)

            try:
                loader = unittest.TestLoader()
                suite = unittest.TestSuite()
                for factory in tests:

                    testcases = factory()
                    if not isinstance(testcases, collections.Iterable):
                        testcases = [testcases]

                    for test in testcases:
                        suite.addTests(loader.loadTestsFromTestCase(test))

                with io.open(report_file, 'wb') as stream:
                    runner = HTMLTestRunner.HTMLTestRunner(
                        stream=stream,
                        title='Treadmill cell checkout',
                        description='Treamdill cell checkout tests'
                    )
                    result = runner.run(suite)

            except Exception as err:  # pylint: disable=W0703
                _LOGGER.exception('Unhandled exception during checkout')

                result = None
                with io.open(report_file, 'wb') as stream:
                    stream.write(str(err).encode('utf8'))
                    traceback.print_exc(file=stream)

            for name in processor:
                plugin_manager.load(
                    'treadmill.checkout.processors', name
                ).process(context.GLOBAL.cell, report_file, result)

            _cleanup(outdir, age)

            total_interval = interval + random.randint(0, randomize)
            _LOGGER.info('Sleep for %s sec.', total_interval)
            time.sleep(total_interval)

    del run_tests
    return run
