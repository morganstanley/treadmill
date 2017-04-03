"""Treadmill REST APIs"""
from __future__ import absolute_import

import os
import logging
import importlib
import pkgutil

import flask
# E0611: Used when a name cannot be found in a module.
# F0401: Used when PyLint has been unable to import a module.
#
# pylint: disable=E0611,F0401
import flask_restplus as restplus

from treadmill import authz
from treadmill.rest import error_handlers
from treadmill import rest
from treadmill import utils
from treadmill import webutils


__path__ = pkgutil.extend_path(__path__, __name__)

_LOGGER = logging.getLogger(__name__)


def init(apis, title=None, cors_origin=None, authz_arg=None):
    """Module initialization."""

    blueprint = flask.Blueprint('v1', __name__)

    api = restplus.Api(blueprint, version='1.0',
                       title=title,
                       description="Treadmill REST API Documentation")

    error_handlers.register(api)

    # load up any external error_handlers
    try:
        err_handlers_plugin = importlib.import_module(
            'treadmill.plugins.rest.error_handlers')
        err_handlers_plugin.init(api)
    except ImportError as err:
        _LOGGER.warn('Unable to load error_handlers plugin: %s', err)

    @blueprint.route('/docs/', endpoint='docs')
    def _swagger_ui():
        """Swagger documentation route"""
        return restplus.apidoc.ui_for(api)

    rest.FLASK_APP.register_blueprint(blueprint)
    rest.FLASK_APP.register_blueprint(restplus.apidoc.apidoc)

    cors = webutils.cors(origin=cors_origin,
                         content_type='application/json',
                         credentials=True)

    @rest.FLASK_APP.after_request
    def _after_request_cors_handler(response):
        """Process all OPTIONS request, thus don't need to add to each app"""
        if flask.request.method != 'OPTIONS':
            return response

        _LOGGER.debug('This is an OPTIONS call')

        def _noop_options():
            """No noop response handler for all OPTIONS"""
            pass

        headers = flask.request.headers.get('Access-Control-Request-Headers')
        options_cors = webutils.cors(origin=cors_origin,
                                     credentials=True,
                                     headers=headers)
        response = options_cors(_noop_options)()
        return response

    def user_clbk():
        """Get current user from the request."""
        return flask.request.environ.get('REMOTE_USER')

    if authz_arg is None:
        authorizer = authz.NullAuthorizer()
    else:
        authorizer = authz.ClientAuthorizer(user_clbk, authz_arg)

    endpoints = []
    for apiname in apis:
        try:
            apimod = apiname.replace('-', '_')
            _LOGGER.info('Loading api: %s', apimod)

            api_restmod = importlib.import_module(
                '.'.join(['treadmill', 'rest', 'api', apimod])
            )
            api_implmod = importlib.import_module(
                '.'.join(['treadmill', 'api', apimod])
            )

            api_impl = api_implmod.init(authorizer)
            endpoint = api_restmod.init(api, cors, api_impl)
            if endpoint is None:
                endpoint = apiname.replace('_', '-').replace('.', '/')
            if not endpoint.startswith('/'):
                endpoint = '/' + endpoint

            endpoints.append(endpoint)

        except ImportError as err:
            _LOGGER.warn('Unable to load %s api: %s', apimod, err)

    return endpoints
