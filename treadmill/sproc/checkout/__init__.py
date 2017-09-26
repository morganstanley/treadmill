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


def _start_webserver(outdir, port):
    """Start web server for report content."""
    utils.drop_privileges()
    app = flask.Flask(__name__)

    @app.route('/checkout')
    def _get_listing():
        """Return list of reports."""
        files = os.listdir(outdir)
        template = """
        <html>
        <body>
            {% for file in files %}
                <a href=/checkout/{{ file }}>{{ file }}</a><br>
            {% endfor %}
        </body>
        </html>
        """
        return flask.render_template_string(template, files=reversed(files))

    @app.route('/checkout/<path:path>')
    def _get_report(path):
        """Return checkout report."""
        if not path:
            return _get_listing()

        complete_path = os.path.join(outdir, path)
        mimetype = 'text/html'
        try:
            with io.open(complete_path) as f:
                return flask.Response(f.read(), mimetype=mimetype)
        except IOError as err:
            return flask.Response(str(err), mimetype=mimetype)

    app.run('0.0.0.0', port=port)


def _start_webserver_daemon(outdir, port):
    """Start web server in separate process."""
    if port == 0:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('0.0.0.0', 0))
        port = sock.getsockname()[1]
        sock.close()

    webserver = multiprocessing.Process(
        target=_start_webserver, args=(outdir, port)
    )
    webserver.daemon = True
    webserver.start()

    return port


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
                  required=False, type=int, default=(60 * 5))
    @click.option('--randomize',
                  help='Optional random interval between tests.',
                  required=False, type=int, default=(60 * 5))
    @click.option('--age',
                  help='Max report age to keep.',
                  default='1d')
    @click.option('--processor',
                  help='Result processing plugin.',
                  type=cli.LIST)
    @click.option('--port', type=int,
                  help='Web server port.')
    def run(outdir, interval, randomize, age, processor, port):
        """Test treadmill infrastructure."""
        del outdir
        del interval
        del randomize
        del age
        del processor
        del port

    @run.resultcallback()
    def run_tests(tests, outdir, interval, randomize, age, processor, port):
        """Test treadmill infrastructure."""

        if port is not None:
            port = _start_webserver_daemon(outdir, port)

        _LOGGER.info('Starting tests: %s', outdir)
        fs.mkdir_safe(outdir)

        while True:

            report_name = '%s.html' % datetime.datetime.isoformat(
                datetime.datetime.now()
            )
            report_file = os.path.join(outdir, report_name)
            report_url = 'http://%s:%s/checkout/%s' % (
                sysinfo.hostname(), port, report_name
            )
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

                with io.open(report_file, 'w') as stream:
                    runner = HtmlTestRunner.HTMLTestRunner(
                        stream=stream,
                        title='Treadmill cell checkout',
                        description='Treamdill cell checkout tests'
                    )
                    result = runner.run(suite)

            except Exception as err:  # pylint: disable=W0703
                _LOGGER.exception('Unhandled exception during checkout')

                result = None
                with io.open(report_file, 'w') as stream:
                    stream.write(str(err))
                    traceback.print_exc(file=stream)

            for name in processor:
                plugin_manager.load(
                    'treadmill.checkout.processors', name
                ).process(context.GLOBAL.cell, report_url, result)

            _cleanup(outdir, age)

            total_interval = interval + random.randint(0, randomize)
            _LOGGER.info('Sleep for %s sec.', total_interval)
            time.sleep(total_interval)

    del run_tests
    return run
