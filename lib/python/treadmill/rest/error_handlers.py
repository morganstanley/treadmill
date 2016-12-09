"""
REST Error Handlers module.

This contains all of the error handlers for possible exceptions being thrown
in our REST endpoints.
"""
from __future__ import absolute_import

import logging
import httplib
import sys

import ldap3
import jsonschema
import kazoo.exceptions

from treadmill import authz
from treadmill import exc
from treadmill import rest


_LOGGER = logging.getLogger(__name__)


def register(api):
    """Register all of the error handlers"""

    @api.errorhandler(authz.AuthorizationError)
    def authorization_exc(err):
        """Authorization exception handler."""
        _LOGGER.exception('exception: %r', err)
        return {'message': err.message,
                'status': httplib.UNAUTHORIZED}, httplib.UNAUTHORIZED

    @api.errorhandler(kazoo.client.NoNodeError)
    def zookeeper_notfound(err):
        """Zookeeper nonode exception handler."""
        _LOGGER.exception('exception: %r', err)
        return {'message': err.message,
                'status': httplib.NOT_FOUND}, httplib.NOT_FOUND

    @api.errorhandler(kazoo.exceptions.KazooException)
    def zookeeper_exc(err):
        """Zookeeper exception handler."""
        _LOGGER.exception('exception: %r', err)
        return {
            'message': err.message,
            'status': httplib.INTERNAL_SERVER_ERROR
        }, httplib.INTERNAL_SERVER_ERROR

    # Flask.errorhandler() only captures exceptions thrown from the same thread
    # in which it is started from; for us this is obviously MainThread so the
    # kazoo exceptions, which are raised from a separate thread are not
    # captured. The below handler intercepts all responses and checks to see if
    # there is any exceptions, if there are and it is a Kazoo exception (at the
    # moment, just NoNodeError), then, then explicitly call
    # "zookeeper_notfound".
    def _handle_threaded_exceptions(resp):
        """Handle Kazoo threaded exceptions"""
        exc_info = sys.exc_info()
        err = exc_info[1]

        if not err:
            return resp

        if err and isinstance(err, kazoo.exceptions.NoNodeError):
            return zookeeper_notfound(err)

        return resp

    rest.FLASK_APP.after_request(_handle_threaded_exceptions)

    @api.errorhandler(ldap3.LDAPEntryAlreadyExistsResult)
    def ldap_found_exc(err):
        """LDAP exception handler."""
        _LOGGER.exception('exception: %r', err)
        return {'message': err.result,
                'status': httplib.NOT_FOUND}, httplib.FOUND

    @api.errorhandler(ldap3.LDAPNoSuchObjectResult)
    def ldap_not_found_exc(err):
        """LDAP exception handler."""
        _LOGGER.exception('err: %r', err)
        return {'message': err.result,
                'status': httplib.NOT_FOUND}, httplib.NOT_FOUND

    @api.errorhandler(jsonschema.exceptions.ValidationError)
    def json_validation_error_exc(err):
        """JSON Schema Validation error exception handler."""
        _LOGGER.exception('exception: %r', err)
        return {'message': err.result,
                'status': httplib.FAILED_DEPENDENCY}, httplib.FAILED_DEPENDENCY

    @api.errorhandler(exc.TreadmillError)
    def treadmill_exc(err):
        """Treadmill exception handler."""
        _LOGGER.exception('exception: %r', err)
        return {'message': err.message,
                'status': httplib.BAD_REQUEST}, httplib.BAD_REQUEST

    def internal_server_error(err):
        """Unhandled exception handler."""
        _LOGGER.exception('exception: %r', err)
        return {
            'message': err.message,
            'status': httplib.INTERNAL_SERVER_ERROR
        }, httplib.INTERNAL_SERVER_ERROR

    @api.errorhandler(Exception)
    def unhandled_exc(err):
        """Unhandled exception handler."""
        return internal_server_error(err)

    del ldap_found_exc
    del ldap_not_found_exc
    del zookeeper_exc
    del json_validation_error_exc
    del authorization_exc
    del unhandled_exc
    del treadmill_exc
