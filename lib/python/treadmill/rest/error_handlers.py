"""
REST Error Handlers module.

This contains all of the error handlers for possible exceptions being thrown
in our REST endpoints.
"""
from __future__ import absolute_import

import logging
import httplib

import ldap3
import jsonschema
import flask
import kazoo.exceptions
import kazoo

from treadmill import authz
from treadmill import rest


_LOGGER = logging.getLogger(__name__)


@rest.FLASK_APP.errorhandler(authz.AuthorizationError)
def authorization_exc(err):
    """Authorization exception handler."""
    _LOGGER.error('exception: %r', err)
    response = flask.jsonify({'message': err.message,
                              'status': httplib.UNAUTHORIZED})

    response.status_code = httplib.UNAUTHORIZED
    return response


@rest.FLASK_APP.errorhandler(kazoo.client.NoNodeError)
def zookeeper_notfound(err):
    """Zookeeper nonode exception handler."""
    _LOGGER.error('exception: %r', err)
    response = flask.jsonify({'message': err.message,
                              'status': httplib.NOT_FOUND})

    response.status_code = httplib.NOT_FOUND
    return response


@rest.FLASK_APP.errorhandler(kazoo.exceptions.KazooException)
def zookeeper_exc(err):
    """Zookeeper exception handler."""
    _LOGGER.error('exception: %r', err)
    response = flask.jsonify({'message': err.message,
                              'status': httplib.INTERNAL_SERVER_ERROR})
    response.status_code = httplib.INTERNAL_SERVER_ERROR
    return response


@rest.FLASK_APP.errorhandler(ldap3.LDAPEntryAlreadyExistsResult)
def ldap_found_exc(err):
    """Zookeeper exception handler."""
    _LOGGER.error('exception: %r', err)
    response = flask.jsonify({'message': err.message,
                              'status': httplib.FOUND})

    response.status_code = httplib.FOUND
    return response


@rest.FLASK_APP.errorhandler(ldap3.LDAPNoSuchObjectResult)
def ldap_not_found_exc(err):
    """Zookeeper exception handler."""
    _LOGGER.error('exception: %r', err)
    response = flask.jsonify({'message': err.message,
                              'status': httplib.NOT_FOUND})

    response.status_code = httplib.NOT_FOUND
    return response


def failed_dependency(err):
    """Generic failed dependency error handler"""
    _LOGGER.error('exception: %r', err)
    response = flask.jsonify({'message': err.message,
                              'status': httplib.FAILED_DEPENDENCY})

    response.status_code = httplib.FAILED_DEPENDENCY
    return response


@rest.FLASK_APP.errorhandler(jsonschema.exceptions.ValidationError)
def json_validation_error_exc(err):
    """JSON Schema Validation error exception handler."""
    return failed_dependency(err)


def internal_server_error(err):
    """Unhandled exception handler."""
    _LOGGER.exception('exception: %r', err)
    response = flask.jsonify({'message': err.message,
                              'status': httplib.INTERNAL_SERVER_ERROR})

    response.status_code = httplib.INTERNAL_SERVER_ERROR
    return response


@rest.FLASK_APP.errorhandler(Exception)
def unhandled_exc(err):
    """Unhandled exception handler."""
    return internal_server_error(err)
