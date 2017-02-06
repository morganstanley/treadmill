"""
REST Error Handlers module.

This contains all of the error handlers for possible exceptions being thrown
in our REST endpoints.
"""


import logging
import http.client

import ldap3
import jsonschema
import kazoo.exceptions
import kazoo

from treadmill import authz
from treadmill import exc


_LOGGER = logging.getLogger(__name__)


def register(api):
    """Register common error handlers."""

    @api.errorhandler(authz.AuthorizationError)
    def _authorization_exc(err):
        """Authorization exception handler."""
        _LOGGER.info('Authorization error: %r', err)
        return {'message': err.message,
                'status': http.client.UNAUTHORIZED}, http.client.UNAUTHORIZED

    @api.errorhandler(kazoo.exceptions.NoNodeError)
    def _zookeeper_notfound(err):
        """Zookeeper nonode exception handler."""
        _LOGGER.info('Zookeeper not found error: %r', err)
        return {'message': 'Resource not found',
                'status': http.client.NOT_FOUND}, http.client.NOT_FOUND

    @api.errorhandler(kazoo.exceptions.NodeExistsError)
    def _zookeeper_exists(err):
        """Zookeeper node exists exception handler."""
        _LOGGER.info('Zookeeper node exists error: %r', err)
        return {'message': 'Resource already exists',
                'status': http.client.FOUND}, http.client.FOUND

    @api.errorhandler(kazoo.exceptions.KazooException)
    def _zookeeper_exc(err):
        """Zookeeper exception handler."""
        _LOGGER.exception('Zookeeper error: %r', err)
        return {
            'message': err.message,
            'status': http.client.INTERNAL_SERVER_ERROR
        }, http.client.INTERNAL_SERVER_ERROR

    @api.errorhandler(ldap3.LDAPEntryAlreadyExistsResult)
    def _ldap_found_exc(err):
        """LDAP exception handler."""
        _LOGGER.info('Ldap already exists error: %r', err)
        return {'message': err.result,
                'status': http.client.FOUND}, http.client.FOUND

    @api.errorhandler(ldap3.LDAPNoSuchObjectResult)
    def _ldap_not_found_exc(err):
        """LDAP exception handler."""
        _LOGGER.exception('Ldap no such object error: %r', err)
        return {'message': err.message,
                'status': http.client.NOT_FOUND}, http.client.NOT_FOUND

    @api.errorhandler(jsonschema.exceptions.ValidationError)
    def _json_validation_error_exc(err):
        """JSON Schema Validation error exception handler."""
        _LOGGER.info('Schema validation error: %r', err)
        return {'message': err.message,
                'status': http.client.BAD_REQUEST}, http.client.BAD_REQUEST

    @api.errorhandler(exc.TreadmillError)
    def _treadmill_exc(err):
        """Treadmill exception handler."""
        _LOGGER.exception('Treadmill error: %r', err)
        return {
            'message': err.message,
            'status': http.client.INTERNAL_SERVER_ERROR
        }, http.client.INTERNAL_SERVER_ERROR

    def _internal_server_error(err):
        """Unhandled exception handler."""
        _LOGGER.exception('exception: %r', err)
        return {
            'message': err.message,
            'status': http.client.INTERNAL_SERVER_ERROR
        }, http.client.INTERNAL_SERVER_ERROR

    @api.errorhandler(Exception)
    def _unhandled_exc(err):
        """Unhandled exception handler."""
        return _internal_server_error(err)
