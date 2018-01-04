"""Cell API proxy sproc module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import random
import re
import socket

import click
import flask

import six
from six.moves import http_client

from ldap3.core import exceptions as ldap_exceptions

from treadmill import admin
from treadmill import cli
from treadmill import context
from treadmill import dnsutils
from treadmill import rest
from treadmill import utils
from treadmill import webutils


REDIR_ALLOWED_PROTOCOLS = ['http']

_LOGGER = logging.getLogger(__name__)


class HttpException(Exception):
    """Base HTTP exception class"""
    status_code = 500

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        """Exception to dictionary"""
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv


class NoLBSetup(HttpException):
    """No LB Setup found exception"""
    status_code = 404


class NoSrvRecords(HttpException):
    """No SRV records found exception"""
    status_code = 404


class RedirNotAllowed(HttpException):
    """Redirection not allowed for protocol"""
    status_code = 400


def setup_server(api_types, sys_campus, cors_origin):
    """Runs the proxy server"""

    campus_re = re.compile('-{}-'.format(sys_campus))

    def _lb_data_to_target(api_protocol, dataarray):
        """Extract target URL from lb data"""
        datadict = {}
        for item in dataarray:
            key, values = item.split('=')
            values = values.split(',')
            datadict[key] = values[0] if len(values) == 1 else values

        vips = [
            vip
            for vip in datadict['vips']
            if campus_re.search(vip)
        ]

        if len(vips):
            host = vips[0]
            hostname = host
            # We need the canonical hostname in the redirected host for the
            # java client, as their MSKerbeors setup requires the canonical
            # name for the requests, which is what is stored in Kerb DN,
            # from what I am told by MSJava
            try:
                hostname, _, _ = socket.gethostbyname_ex(host)
            except socket.error:
                # This is ok to pass, we will just use the hostname
                pass

            return '{}://{}:{}'.format(api_protocol,
                                       hostname,
                                       datadict['port'])
        else:
            return None

    def _get_url_lb(api_type, api_protocol, cellname):
        """Get url based on an existing lbendpoint, use "this" SYS_CAMPUS
           since requests are supposed to pass through GTM, which resolves to
           the right region for the user"""
        admin_ag = admin.AppGroup(context.GLOBAL.ldap.conn)
        lbendpoints = admin_ag.get('*.{}api.{}'.format(api_type,
                                                       cellname),
                                   'lbendpoint')
        datadict = _lb_data_to_target(api_protocol, lbendpoints['data'])
        return datadict

    def _get_url_srv(target):
        """Get first working URL from SRV records"""
        srv_recs = dnsutils.srv(
            target + '.' + context.GLOBAL.dns_domain,
            context.GLOBAL.dns_server
        )

        if not srv_recs:
            raise NoSrvRecords('No SRV records found for {}'.format(target))

        srv_rec = random.choice(srv_recs)
        return dnsutils.srv_rec_to_url(srv_rec, target)

    def _get_url(rtype, api_type, api_protocol, cellname):
        target_url = None

        if rtype == 'lb':
            try:
                target_url = _get_url_lb(api_type, api_protocol, cellname)
            except ldap_exceptions.LDAPNoSuchObjectResult:
                raise NoLBSetup('No LB setup for {} and {} protocol'.format(
                    api_type, api_protocol))

            return target_url

        target_url = _get_url_srv(
            '_{}._tcp.{}api.{}.cell'.format(
                api_protocol,
                api_type,
                cellname
            )
        )

        return target_url

    def _api_path_handler_redir(rtype, api_type, api_protocol, cellname,
                                path=None):
        """Handle API call with redirect"""

        if api_protocol not in REDIR_ALLOWED_PROTOCOLS:
            raise RedirNotAllowed(
                'Redirection not allowed for {} protocol'.format(api_protocol)
            )

        target_url = _get_url(rtype, api_type, api_protocol, cellname)
        if path is not None:
            target_url = '{}/{}'.format(target_url,
                                        utils.encode_uri_parts(path))

        if flask.request.query_string:
            target_url += '?{}'.format(flask.request.query_string)

        _LOGGER.info('Redirecting to %s', target_url)

        return flask.redirect(target_url, code=http_client.TEMPORARY_REDIRECT)

    def _api_path_handler_json(rtype, api_type, api_protocol, cellname,
                               path=None):
        """Handle API call with JSON response"""

        target_url = _get_url(rtype, api_type, api_protocol, cellname)
        if path is not None:
            target_url = '{}/{}'.format(target_url,
                                        utils.encode_uri_parts(path))

        if flask.request.query_string:
            target_url += '?{}'.format(flask.request.query_string)

        _LOGGER.info('Sending SRV to %s', target_url)
        return flask.jsonify({'target': target_url})

    def _handle_exception(exception):
        """Generic exception handler for this app"""
        response = flask.jsonify(exception.to_dict())
        response.status_code = exception.status_code
        return response

    @rest.FLASK_APP.errorhandler(NoSrvRecords)
    def _handle_no_srv_records(exception):
        """Handle NoSrvRecords exception"""
        return _handle_exception(exception)

    @rest.FLASK_APP.errorhandler(NoLBSetup)
    def _handle_no_lb(exception):
        """Handle NoLBSetup exception"""
        return _handle_exception(exception)

    @rest.FLASK_APP.errorhandler(RedirNotAllowed)
    def _handle_redir_not_allowed(exception):
        """Handle RedirNotAllowed exception"""
        return _handle_exception(exception)

    options = dict(methods=['OPTIONS', 'HEAD', 'GET', 'POST', 'PUT', 'DELETE'])
    cors = webutils.cors(cors_origin, credentials=True)

    for atype, aprot in six.iteritems(api_types):
        for rtype in ['lb', 'srv']:
            # Redirect rule
            rest.FLASK_APP.add_url_rule(
                '/redir/{}/{}/<cellname>'.format(rtype, atype),
                endpoint='redir_{}_{}_cell'.format(rtype, atype),
                view_func=cors(
                    lambda cellname, cr=rtype, ca=atype, cp=aprot:
                    _api_path_handler_redir(
                        cr, ca, cp, cellname
                    )
                ),
                **options
            )
            rest.FLASK_APP.add_url_rule(
                '/redir/{}/{}/<cellname>/<path:path>'.format(rtype, atype),
                endpoint='redir_{}_{}_cell_path'.format(rtype, atype),
                view_func=cors(
                    lambda cellname, path, cr=rtype, ca=atype, cp=aprot:
                    _api_path_handler_redir(
                        cr, ca, cp, cellname, path
                    )
                ),
                **options
            )
            # JSON rule
            rest.FLASK_APP.add_url_rule(
                '/json/{}/{}/<cellname>'.format(rtype, atype),
                endpoint='json_{}_{}_cell'.format(rtype, atype),
                view_func=cors(
                    lambda cellname, cr=rtype, ca=atype, cp=aprot:
                    _api_path_handler_json(
                        cr, ca, cp, cellname
                    )
                ),
                **options
            )
            rest.FLASK_APP.add_url_rule(
                '/json/{}/{}/<cellname>/<path:path>'.format(rtype, atype),
                endpoint='json_{}_{}_cell_path'.format(rtype, atype),
                view_func=cors(
                    lambda cellname, path, cr=rtype, ca=atype, cp=aprot:
                    _api_path_handler_json(
                        cr, ca, cp, cellname, path
                    )
                ),
                **options
            )


def init():
    """Top level command handler."""

    @click.command(name='api-discover')
    @click.option('-p', '--port', required=True)
    @click.option('-a', '--auth', type=click.Choice(['spnego']))
    @click.option('--api-types',
                  type=cli.DICT,
                  help='list of key value pairs'
                       ' mapping API type to protocol eg. cell=http,ws=ws')
    @click.option('--sys-campus', required=True, envvar='SYS_CAMPUS')
    @click.option('-c', '--cors-origin', help='CORS origin REGEX',
                  required=True)
    def server(port, auth, api_types, sys_campus, cors_origin):
        """Set up server"""
        setup_server(api_types, sys_campus, cors_origin)
        random.seed()
        api_paths = ['/{}'.format(atype) for atype in api_types.keys()]
        rest_server = rest.TcpRestServer(port, auth_type=auth,
                                         protect=api_paths)
        rest_server.run()

    return server
