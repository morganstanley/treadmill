"""REST Error Handlers module.

This contains all of the error handlers for possible exceptions being thrown
in our REST endpoints.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import kazoo
import kazoo.exceptions
import jsonschema
from ldap3.core import exceptions as ldap_exceptions

from six.moves import http_client

from treadmill.admin import exc as admin_exceptions
from treadmill import authz
from treadmill import exc
from treadmill import webutils


_LOGGER = logging.getLogger(__name__)


def register(api):
    """Register common error handlers."""

    # TODO: flask.errorhandler is **flaky**. This whole error handling method
    #       needs to be re-written.
    #
    #       Depending on some randomness, they are either registered, or not.
    #
    #       Example of randomness can be calling "print" inside the handler,
    #       or similar non-significant code changes.
    def _cors_headers():
        return webutils.cors_make_headers(base_origin='.*',
                                          max_age=21600,
                                          credentials=True,
                                          content_type='application/json')

    @api.errorhandler(authz.AuthorizationError)
    def _authorization_exc(err):
        """Authorization exception handler."""
        _LOGGER.info('Authorization error: %r', str(err))
        resp = {'message': str(err),
                'status': http_client.FORBIDDEN}
        return resp, http_client.FORBIDDEN, _cors_headers()

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
                'status': http_client.CONFLICT}
        return resp, http_client.CONFLICT, _cors_headers()

    @api.errorhandler(kazoo.exceptions.KazooException)
    def _zookeeper_exc(err):
        """Zookeeper exception handler."""
        _LOGGER.exception('Zookeeper error: %r', err)
        resp = {
            'message': str(err),
            'status': http_client.INTERNAL_SERVER_ERROR
        }
        return resp, http_client.INTERNAL_SERVER_ERROR, _cors_headers()

    @api.errorhandler(ldap_exceptions.LDAPEntryAlreadyExistsResult)
    def _ldap_found_exc(err):
        """LDAP exception handler."""
        _LOGGER.info('Ldap already exists error: %r', err)
        resp = {'message': err.result,
                'status': http_client.CONFLICT}
        return resp, http_client.CONFLICT, _cors_headers()

    @api.errorhandler(ldap_exceptions.LDAPNoSuchObjectResult)
    def _ldap_not_found_exc(err):
        """LDAP exception handler."""
        _LOGGER.exception('Ldap no such object error: %r', err)
        resp = {'message': str(err),
                'status': http_client.NOT_FOUND}
        return resp, http_client.NOT_FOUND, _cors_headers()

    @api.errorhandler(admin_exceptions.AlreadyExistsResult)
    def _admin_found_exc(err):
        """Admin exception handler."""
        _LOGGER.info('Already exists error: %r', err)
        resp = {'message': str(err),
                'status': http_client.CONFLICT}
        return resp, http_client.CONFLICT, _cors_headers()

    @api.errorhandler(admin_exceptions.NoSuchObjectResult)
    def _admin_not_found_exc(err):
        """Admin exception handler."""
        _LOGGER.exception('Admin no such object error: %r', err)
        resp = {'message': str(err),
                'status': http_client.NOT_FOUND}
        return resp, http_client.NOT_FOUND, _cors_headers()

    @api.errorhandler(exc.LocalFileNotFoundError)
    def _file_not_found_exc(err):
        """Nodeinfo/local module exception handler."""
        _LOGGER.exception('File not found error: %r', err)
        resp = {'message': str(err),
                'status': http_client.NOT_FOUND}
        return resp, http_client.NOT_FOUND, _cors_headers()

    @api.errorhandler(jsonschema.exceptions.ValidationError)
    def _json_validation_error_exc(err):
        """JSON Schema Validation error exception handler."""
        _LOGGER.info('Schema validation error: %r', err)
        resp = {'message': str(err),
                'status': http_client.BAD_REQUEST}
        return resp, http_client.BAD_REQUEST, _cors_headers()

    @api.errorhandler(exc.InvalidInputError)
    def _invalid_input_exc(err):
        """InvalidInputError exception handler."""
        _LOGGER.exception('Invalid input error: %r', err)
        resp = {
            'message': str(err),
            'status': http_client.BAD_REQUEST
        }
        return resp, http_client.BAD_REQUEST, _cors_headers()

    @api.errorhandler(exc.QuotaExceededError)
    def _quota_exceeded_exc(err):
        """QuotaExceededError exception handler."""
        _LOGGER.info('Quota exceeded: %r', err)
        resp = {
            'message': str(err),
            'status': http_client.BAD_REQUEST
        }
        return resp, http_client.BAD_REQUEST, _cors_headers()

    @api.errorhandler(exc.NotFoundError)
    def _not_found_exc(err):
        """NotFoundError exception handler."""
        _LOGGER.exception('Not found error: %r', err)
        resp = {
            'message': str(err),
            'status': http_client.NOT_FOUND
        }
        return resp, http_client.NOT_FOUND, _cors_headers()

    @api.errorhandler(exc.FoundError)
    def _found_exc(err):
        """Found exception handler."""
        _LOGGER.info('Resource already exists: %r', err)
        resp = {
            'message': str(err),
            'status': http_client.CONFLICT
        }
        return resp, http_client.CONFLICT, _cors_headers()

    @api.errorhandler(exc.TreadmillError)
    def _treadmill_exc(err):
        """Treadmill exception handler."""
        _LOGGER.exception('Treadmill error: %r', err)
        resp = {
            'message': str(err),
            'status': http_client.INTERNAL_SERVER_ERROR
        }
        return resp, http_client.INTERNAL_SERVER_ERROR, _cors_headers()
