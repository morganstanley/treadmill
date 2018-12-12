"""Treadmill REST APIs.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import flask
import flask_restplus as restplus

from treadmill import api as api_mod
from treadmill import authz
from treadmill import plugin_manager
from treadmill import rest
from treadmill import webutils
from treadmill.rest import error_handlers

_LOGGER = logging.getLogger(__name__)


def base_api(title=None, cors_origin=None):
    """Create base_api object"""
    blueprint = flask.Blueprint('v1', __name__)

    api = restplus.Api(blueprint, version='1.0',
                       title=title,
                       description='Treadmill REST API Documentation')

    error_handlers.register(api)

    # load up any external error_handlers
    for module in plugin_manager.load_all('treadmill.rest.error_handlers'):
        module.init(api)

    @blueprint.route('/docs/', endpoint='docs')
    def _swagger_ui():
        """Swagger documentation route"""
        return restplus.apidoc.ui_for(api)

    rest.FLASK_APP.register_blueprint(blueprint)
    rest.FLASK_APP.register_blueprint(restplus.apidoc.apidoc)

    cors = webutils.cors(origin=cors_origin,
                         content_type='application/json',
                         credentials=True)

    @rest.FLASK_APP.before_request
    def _before_request_user_handler():
        user = flask.request.environ.get('REMOTE_USER')
        if user:
            flask.g.user = user

    @rest.FLASK_APP.after_request
    def _after_request_cors_handler(response):
        """Process all OPTIONS request, thus don't need to add to each app"""
        if flask.request.method != 'OPTIONS':
            return response

        _LOGGER.debug('This is an OPTIONS call')

        def _noop_options():
            """No noop response handler for all OPTIONS.
            """

        headers = flask.request.headers.get('Access-Control-Request-Headers')
        options_cors = webutils.cors(origin=cors_origin,
                                     credentials=True,
                                     headers=headers)
        response = options_cors(_noop_options)()
        return response

    return (api, cors)


def get_authorizer(authz_arg=None):
    """Get authozrizer by argujents"""

    def user_clbk():
        """Get current user from the request."""
        return flask.g.get('user')

    if authz_arg is None:
        authorizer = authz.NullAuthorizer()
    else:
        authorizer = authz.ClientAuthorizer(user_clbk, authz_arg)
    return authorizer


def init(apis, title=None, cors_origin=None, authz_arg=None):
    """Module initialization."""
    (api, cors) = base_api(title, cors_origin)

    authorizer = get_authorizer(authz_arg)
    ctx = api_mod.Context(authorizer=authorizer)

    endpoints = []
    for apiname, apiconfig in apis.items():
        try:
            _LOGGER.info('Loading api: %s', apiname)

            api_cls = plugin_manager.load('treadmill.api', apiname).API
            api_impl = ctx.build_api(api_cls, apiconfig)
            endpoint = plugin_manager.load(
                'treadmill.rest.api', apiname).init(api, cors, api_impl)

            if endpoint is None:
                endpoint = apiname.replace('_', '-').replace('.', '/')
            if not endpoint.startswith('/'):
                endpoint = '/' + endpoint

            _LOGGER.info('Adding endpoint %s', endpoint)
            endpoints.append(endpoint)

        except ImportError as err:
            _LOGGER.warning('Unable to load %s api: %s', apiname, err)

    return endpoints
