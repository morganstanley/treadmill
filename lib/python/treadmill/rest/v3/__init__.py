"""Treadmill v3 REST."""
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
import flask.ext.restplus as restplus

from ... import rest
from ... import webutils

from treadmill import authz
from treadmill import utils


__path__ = pkgutil.extend_path(__path__, __name__)

_LOGGER = logging.getLogger(__name__)


def init(apis):
    """Module initialization."""

    blueprint = flask.Blueprint('v3', __name__, url_prefix='/v3')

    api = restplus.Api(blueprint, version='3.0', ui=False,
                       title="Treadmill's API Server - v3",
                       description="Treadmill's API server")

    @blueprint.route('/docs/', endpoint='docs')
    def _swagger_ui():
        """Swagger documentation route"""
        return restplus.apidoc.ui_for(api)

    rest.FLASK_APP.register_blueprint(blueprint)
    rest.FLASK_APP.register_blueprint(restplus.apidoc.apidoc)

    # TODO: origin must be configurable.
    cors = webutils.cors(origin='.*',
                         content_type='application/json',
                         credentials=True)

    def user_clbk():
        """Get current user from the request."""
        return flask.request.environ.get('REMOTE_USER')

    authorizer = authz.PluginAuthorizer(user_clbk)

    for apiname in apis:
        try:
            apimod = apiname.replace('-', '_')
            _LOGGER.info('Loading api: %s', apimod)

            api_restmod = importlib.import_module(
                'treadmill.rest.v3.' + apimod)
            api_implmod = importlib.import_module(
                'treadmill.api.' + apimod)

            api_impl = api_implmod.init(authorizer)
            api_restmod.init(api, cors, api_impl)

        except ImportError as err:
            _LOGGER.warn('Unable to load %s api: %s', apimod, err)

    return ['/v3/' + apimod.replace('_', '-') for apimod in apis]
