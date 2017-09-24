"""REST Error Handlers module.

This contains all of the error handlers for possible exceptions being thrown
in our REST endpoints.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import jsonschema
import kazoo
import kazoo.exceptions
import ldap3

from six.moves import http_client

from treadmill import authz
from treadmill import exc
from treadmill import webutils


_LOGGER = logging.getLogger(__name__)


def register(api):
    """Register common error handlers."""

    def _cors_headers():
        return webutils.cors_make_headers(base_origin='.*',
                                          max_age=21600,
                                          credentials=True,
                                          content_type='application/json')

    @api.errorhandler(authz.AuthorizationError)
    def _authorization_exc(err):
        """Authorization exception handler."""
        _LOGGER.info('Authorization error: %r', err)
        resp = {'message': err.message,
                'status': http_client.UNAUTHORIZED}
        return resp, http_client.UNAUTHORIZED, _cors_headers()

    @api.errorhandler(kazoo.exceptions.NoNodeError)
    def _zookeeper_notfound(err):
        """Zookeeper nonode exception handler."""
        _LOGGER.info('Zookeeper not found error: %r', err)
        resp = {'message': 'Resource not found',
                'status': http_client.NOT_FOUND}
        return resp, http_client.NOT_FOUND, _cors_headers()

    @api.errorhandler(kazoo.exceptions.NodeExistsError)
    def _zookeeper_exists(err):
        """Zookeeper node exists exception handler."""
        _LOGGER.info('Zookeeper node exists error: %r', err)
        resp = {'message': 'Resource already exists',
                'status': http_client.FOUND}
        return resp, http_client.FOUND, _cors_headers()

    @api.errorhandler(kazoo.exceptions.KazooException)
    def _zookeeper_exc(err):
        """Zookeeper exception handler."""
        _LOGGER.exception('Zookeeper error: %r', err)
        resp = {
            'message': err.message,
            'status': http_client.INTERNAL_SERVER_ERROR
        }
        return resp, http_client.INTERNAL_SERVER_ERROR, _cors_headers()

    @api.errorhandler(ldap3.LDAPEntryAlreadyExistsResult)
    def _ldap_found_exc(err):
        """LDAP exception handler."""
        _LOGGER.info('Ldap already exists error: %r', err)
        resp = {'message': err.result,
                'status': http_client.FOUND}
        return resp, http_client.FOUND, _cors_headers()

    @api.errorhandler(ldap3.LDAPNoSuchObjectResult)
    def _ldap_not_found_exc(err):
        """LDAP exception handler."""
        _LOGGER.exception('Ldap no such object error: %r', err)
        resp = {'message': err.message,
                'status': http_client.NOT_FOUND}
        return resp, http_client.NOT_FOUND, _cors_headers()

    @api.errorhandler(exc.LocalFileNotFoundError)
    def _file_not_found_exc(err):
        """Nodeinfo/local module exception handler."""
        _LOGGER.exception('File not found error: %r', err)
        resp = {'message': err.message,
                'status': http_client.NOT_FOUND}
        return resp, http_client.NOT_FOUND, _cors_headers()

    @api.errorhandler(jsonschema.exceptions.ValidationError)
    def _json_validation_error_exc(err):
        """JSON Schema Validation error exception handler."""
        _LOGGER.info('Schema validation error: %r', err)
        resp = {'message': err.message,
                'status': http_client.BAD_REQUEST}
        return resp, http_client.BAD_REQUEST, _cors_headers()

    @api.errorhandler(exc.InvalidInputError)
    def _invalid_input_exc(err):
        """InvalidInputError exception handler."""
        _LOGGER.exception('Invalid input error: %r', err)
        resp = {
            'message': err.message,
            'status': http_client.BAD_REQUEST
        }
        return resp, http_client.BAD_REQUEST, _cors_headers()

    @api.errorhandler(exc.NotFoundError)
    def _not_found_exc(err):
        """NotFoundError exception handler."""
        _LOGGER.exception('Not found error: %r', err)
        resp = {
            'message': err.message,
            'status': http_client.NOT_FOUND
        }
        return resp, http_client.NOT_FOUND, _cors_headers()

    @api.errorhandler(exc.FoundError)
    def _found_exc(err):
        """Found exception handler."""
        _LOGGER.info('Resource already exists: %r', err)
        resp = {
            'message': err.message,
            'status': http_client.FOUND
        }
        return resp, http_client.FOUND, _cors_headers()

    @api.errorhandler(exc.TreadmillError)
    def _treadmill_exc(err):
        """Treadmill exception handler."""
        _LOGGER.exception('Treadmill error: %r', err)
        resp = {
            'message': err.message,
            'status': http_client.INTERNAL_SERVER_ERROR
        }
        return resp, http_client.INTERNAL_SERVER_ERROR, _cors_headers()

    def _internal_server_error(err):
        """Unhandled exception handler."""
        _LOGGER.exception('exception: %r', err)
        resp = {
            'message': err.message,
            'status': http_client.INTERNAL_SERVER_ERROR
        }
        return resp, http_client.INTERNAL_SERVER_ERROR, _cors_headers()

    @api.errorhandler(Exception)
    def _unhandled_exc(err):
        """Unhandled exception handler."""
        return _internal_server_error(err)
