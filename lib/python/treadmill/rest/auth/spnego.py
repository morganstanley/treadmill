"""Implementation of SPNEGO wsgi middleware."""

import functools
import logging
import re

import base64
import gssapi  # pylint: disable=import-error

from werkzeug import local
from werkzeug.wrappers import BaseRequest, BaseResponse


_LOGGER = logging.getLogger(__name__)

_AUTH_ERROR = functools.partial(BaseResponse, status=500)

_FORBIDDEN = functools.partial(BaseResponse, status=403)

_UNAUTHORIZED = functools.partial(BaseResponse, status=401)


def wrap(wsgi_app, protect):
    """Wrap FLASK app in webauthd middleware."""
    _LOGGER.info('Loading spnego auth.')

    unprotected_paths = ['/']
    unprotected_methods = ['OPTIONS']
    protected_paths = []

    if protect:
        protected_paths.extend(protect)

    local_manager = local.LocalManager([SpnegoAuth.LOCALS])
    app = SpnegoAuth(
        wsgi_app,
        protected_paths=protected_paths,
        unprotected_paths=unprotected_paths,
        unprotected_methods=unprotected_methods,
        unprotected_is_regex=False
    )

    return local_manager.make_middleware(app)


class SpnegoAuth:
    """SPNEGO authentication implementation."""

    LOCALS = local.Local()

    def __init__(self, wrapped,
                 protected_paths=(), unprotected_paths=(),
                 unprotected_methods=(),
                 unprotected_is_regex=False):
        """
        :param protected_paths:
            Provide a list of path for which this module should enforce auth
            (e.g. '/login')
        :param wad_cnx_settings:
            Tuple connection settings the WebAuthD daemon (e.g. ('inet',
            [port]) or ('unix', [path]))
        :param unprotected_is_regex:
            Whether unprotected_paths parameter contains regexes (default:
            False)
        """
        self._wrapped = wrapped

        # build a re like this '^(/path1(/.*)?|/path2(/.*)?|/path3(/.*)?)$'
        # Note that empty protected_paths matches *EVERY* paths
        self.protected_paths_re = re.compile(
            r'^(:?' +
            r'(:?/.*)?|'.join(protected_paths) +
            r'(:?/.*)?)$'
        )

        if unprotected_paths:
            if not unprotected_is_regex:
                unprotected_paths = [
                    path + '(:?/.*)?' for path in unprotected_paths
                ]
            self.unprotected_paths_re = re.compile(
                r'^(:?' +
                r'|'.join(unprotected_paths) +
                r')$'
            )
        else:
            self.unprotected_paths_re = None

        self.unprotected_methods = unprotected_methods

        # Print WebAuthD version for information
        _LOGGER.info('Protecting paths: %r',
                     self.protected_paths_re.pattern)
        _LOGGER.info('Unprotecting paths: %r',
                     (self.unprotected_paths_re.pattern
                      if self.unprotected_paths_re is not None
                      else None))
        _LOGGER.info('Unprotecting methods: %r', self.unprotected_methods)

    def _wrapped_authenticated(self, auth_user, auth_token=None):

        def _wrapped(environ, start_response):
            environ['REMOTE_USER'] = auth_user

            # TODO: when is auth token every none?
            if auth_token:
                def spnego_start_response(status, headers, exc_info=None):
                    """Initial spnego response."""
                    headers.append(
                        ('WWW-Authenticate', 'Negotiate %s' % auth_token)
                    )
                    return start_response(status, headers, exc_info)
            else:
                spnego_start_response = start_response

            return self._wrapped(environ, spnego_start_response)

        return _wrapped

    def _auth_spnego(self, request):
        """Perform SPNEGO authentication.
        """
        if 'Authorization' not in request.headers:
            # Send the SPNEGO Negociate challenge
            _LOGGER.debug("Sending SPNEGO Negotiate request")
            resp = BaseResponse(status=401)
            resp.headers['WWW-Authenticate'] = 'Negotiate'
            return resp

        # We have authorization headers
        auth_type, auth_chal = request.headers['Authorization'].split(' ', 3)
        if auth_type != 'Negotiate':
            return _UNAUTHORIZED('Invalid authorization header.')

        _LOGGER.debug("Received SPNEGO Negociate token: %r", auth_chal)
        try:
            if not hasattr(self.LOCALS, 'ctx'):
                # pylint: disable=assigning-non-slot
                self.LOCALS.ctx = gssapi.SecurityContext(
                    creds=None, usage='accept'
                )
                _LOGGER.debug('Init security context.')

            in_token = base64.standard_b64decode(auth_chal)
            out_token = self.LOCALS.ctx.step(in_token)
            auth_token = base64.b64encode(out_token)

            if not self.LOCALS.ctx.complete:
                _LOGGER.debug("Sending SPNEGO Negotiate (continue).")
                resp = BaseResponse(status=401)
                resp.headers['WWW-Authenticate'] = 'Negotiate %s' % auth_token
                return resp

            # GSSAPI negotiation completed.
            auth_user = str(self.LOCALS.ctx.initiator_name)
            _LOGGER.info('Authenticated user: %s', auth_user)

            return self._wrapped_authenticated(auth_user, auth_token)

        # pylint: disable=c-extension-no-member
        except gssapi.raw.misc.GSSError as err:
            _LOGGER.warning('Unhandled exception: %s', str(err))
            return _UNAUTHORIZED(str(err))

    def wsgi_app(self, environ, start_response):
        """WSGI middleware main entry point.
        """
        request = BaseRequest(environ)

        if request.method in self.unprotected_methods:
            return self._wrapped(environ, start_response)

        if not self.protected_paths_re.match(request.path):
            return self._wrapped(environ, start_response)

        if (self.unprotected_paths_re is not None and
                self.unprotected_paths_re.match(request.path)):
            return self._wrapped(environ, start_response)

        _LOGGER.info('Authenticating access to %s', request.path)
        app = self._auth_spnego(request)
        return app(environ, start_response)

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)
