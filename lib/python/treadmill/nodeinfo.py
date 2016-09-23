"""Web server displaing node information."""
from __future__ import absolute_import

import os

import glob
import logging

import flask
import yaml

from . import rrdutils


_LOGGER = logging.getLogger(__name__)


def _cat(filename):
    """Returns file content."""
    _LOGGER.info('cat %s', filename)
    try:
        with open(filename) as f:
            return '<pre>' + f.read() + '</pre>'
    except:  # pylint: disable=W0702
        return 'Not found.', 404


class _RequestHandler(object):
    """Request handler implementation."""

    def __init__(self, approot):
        self.approot = approot
        _LOGGER.info('approot: %s', self.approot)

    def root_handler(self):
        """Nodeinfo root handler."""
        return flask.jsonify({'links': [
            '/_admin/log',
            '/running'
        ]})

    def running_list(self):
        """Returns list of running apps."""
        apps = [os.path.basename(app) for app in
                glob.glob(os.path.join(self.approot, 'running', '*'))]
        return flask.jsonify({'apps': apps})

    def running_get(self, appname):
        """Displays running application manifest."""
        app_yml = os.path.join(self.approot, 'running', appname, 'app.yml')
        if os.path.exists(app_yml):
            with open(app_yml) as f:
                manifest = yaml.load(f.read())
                return flask.jsonify(manifest)
        else:
            return flask.jsonify({'_error': 'Not found.'})

    def admin_log_list(self):
        """Returns list of available logs."""
        services_root = os.path.join(self.approot, 'init', '*')
        services = [os.path.basename(path)
                    for path in glob.glob(services_root)]
        return flask.jsonify({'log': services})

    def admin_log_get(self, service, log):
        """Returns content of log file."""
        logtype = 'log.' + log
        return _cat(os.path.join(self.approot, 'init', service, logtype,
                                 'current'))

    def metrics_get(self, appname):
        """Returns app metrics (rrd file)."""
        name, instance = appname.split('#')
        _LOGGER.info('app metrics: %s', appname)
        match = glob.glob(os.path.join(self.approot, 'metrics', 'apps',
                                       '-'.join([name, instance, '*'])))
        if match:
            rrd = match[0]
            _LOGGER.info('found match: %s', rrd)
            rrdutils.flush_noexc(rrd)
            return flask.send_file(rrd,
                                   attachment_filename=os.path.basename(rrd),
                                   as_attachment=True)

    def core_metrics_get(self, svc):
        """Returns core metrics rrd file."""
        rrd = os.path.join(self.approot, 'metrics', 'core', '%s.rrd' % svc)
        _LOGGER.info('core metrics: %s, %s', svc, rrd)
        rrdutils.flush_noexc(rrd)
        return flask.send_file(rrd,
                               attachment_filename=os.path.basename(rrd),
                               as_attachment=True)


def run(approot, port):
    """Runs the nodeinfo web server."""

    ws = flask.Flask(__name__)
    impl = _RequestHandler(approot)

    @ws.route('/')
    def _root_handler():
        """Nodeinfo root handler."""
        return impl.root_handler()

    @ws.route('/running')
    def _running_list():
        """Returns list of running apps."""
        return impl.running_list()

    @ws.route('/running/<appname>')
    def _running_get(appname):
        """Displays running application manifest."""
        return impl.running_get(appname)

    @ws.route('/metrics/apps/<appname>')
    def _metrics_get(appname):
        """Downloads app rrd file."""
        return impl.metrics_get(appname)

    @ws.route('/metrics/core/<service>')
    def _core_metrics_get(service):
        """Downloads core services rrd file."""
        return impl.core_metrics_get(service)

    @ws.route('/_admin/log')
    def _admin_log_list():
        """Returns list of available logs."""
        return impl.admin_log_list()

    @ws.route('/_admin/log/<service>/<log>')
    def _admin_log_get(service, log):
        """Returns content of log file."""
        return impl.admin_log_get(service, log)

    ws.run(host='0.0.0.0', port=port)
