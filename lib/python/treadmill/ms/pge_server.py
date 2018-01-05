"""Treadmill PGE service
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import json
import os

import flask

from treadmill import authz
from treadmill import dist

from treadmill.ms import msdependencies  # pylint: disable=unused-import

import pgelite

_LOGGER = logging.getLogger(__name__)


class Server(object):
    """module for pge http service"""

    def __init__(self, policy=None):
        self.app = flask.Flask(__name__)
        self.user = None

        if policy is None:
            policy = os.path.join(dist.TREADMILL, 'etc/policy/policy.pro')
        _LOGGER.debug('policy: %r', policy)

        try:
            pge = PGEAuthorizer(policy)
        except Exception:
            _LOGGER.exception('Unable to load authz plugin.')
            raise

        @self.app.route('/<user>/<action>/<resource>', methods=['POST'])
        def auth(user, action, resource):
            """Handler for PGE authorization query"""
            _LOGGER.debug('user: %r', user)
            _LOGGER.debug('action: %r', action)
            _LOGGER.debug('resource: %r', resource)

            args = []
            payload = flask.request.get_json(force=True)

            _LOGGER.debug('auth payload: %r', payload.__class__)
            if 'pk' in payload:
                args.append(payload['pk'])

            if 'payload' in payload:
                if not args:
                    args.append(None)

                args.append(payload['payload'])

            _LOGGER.debug('%s, %s, %s, %r', user, resource, action, args)
            authorized = True
            annotations = []
            status = 200
            try:
                pge.authorize(user, resource, action, args, None)
            except authz.AuthorizationError as err:
                authorized = False
                annotations = err.annotations
            except pgelite.PGELiteException as err:
                authorized = False
                annotations = str(err)
                status = 500

            return flask.Response(
                json.dumps({'auth': authorized, 'annotations': annotations}),
                status=status,
                mimetype='application/json'
            )

        del auth

    def _user_clbk(self):
        return self.user


class PGEAuthorizer(object):
    """PGE authorizer."""

    def __init__(self, policy):
        self.pge = pgelite.PGELite(policy)

    def authorize(self, user, resource, action, args, _kwargs):
        """Authorize user/resource/action using PGE."""

        resource = resource.split('.').pop()

        # PGE API can't handle None.
        if user is None:
            user = ''

        # TODO: was not able to find setting in wsgi_middleware to
        #                strip the user domain.
        if user.find('@') > 0:
            user = user[:user.find('@')]

        # Defaults for primary key and payload.
        pk = ''
        payload = json.dumps({})

        nargs = len(args)
        if nargs > 0:
            pk = str(args[0])
        if nargs > 1:
            payload = json.dumps(args[1])

        _LOGGER.debug('pge authorize: %s, %s, %s, %s, %s',
                      user, action, resource, pk, payload)

        authq = self.pge.AuthQuery('User', action, resource, ['Pk', 'Payload'])
        authq.set('User', user)
        authq.set('Pk', pk)
        authq.set('Payload', payload)

        authorized = authq.match()
        authq.close()

        if not authorized:
            raise authz.AuthorizationError(self._explain())

    def _explain(self):
        """Construct PGE explain message."""
        annotations = []
        authq = self.pge.Explain()
        while authq.match():
            reason = authq.result() + ': ' + authq.why()
            if reason not in annotations:
                annotations.append(reason)
        authq.close()
        annotations.reverse()
        return annotations
