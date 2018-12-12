"""Flask method decorators and other web utilities.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import functools
import gzip
import io
import json
import logging
import re
import shutil

import flask
import six
import tornado
import tornado.httpserver
import tornado.wsgi

from treadmill import utils

_LOGGER = logging.getLogger(__name__)


def add_dependencies():
    """Load (imports) flask dependencies.
    """


def as_json(func):
    """Marshalls function output as json."""
    @functools.wraps(func)
    def decorated_function(*args, **kwargs):
        """Marshalls function output as json."""
        return json.dumps(func(*args, **kwargs))

    return decorated_function


def cors_domain_match(base_domain):
    """Backward compatability, where * is used to respond to all"""
    if base_domain == '*':
        return base_domain

    origin_re = re.compile(r'https?://%s' % base_domain)
    origin = None

    environ = flask.request.environ

    key = 'HTTP_ORIGIN'
    if key in environ.keys():
        origin = environ[key]
    else:
        protocol = environ['SERVER_PROTOCOL'].split('/')[0].lower()
        origin = '{0}://{1}'.format(protocol,
                                    environ['HTTP_HOST'])

    if origin and origin_re.match(origin):
        return origin
    else:
        return None


def cors_make_headers(base_origin,
                      max_age,
                      credentials,
                      content_type,
                      headers=None,
                      methods=None):
    """Create CORS headers from request environment variables"""

    environ = flask.request.environ

    if methods is None:
        methods = [environ['REQUEST_METHOD']]

    hdr = {}
    hdr['Access-Control-Allow-Origin'] = cors_domain_match(base_origin)
    hdr['Access-Control-Allow-Methods'] = methods
    hdr['Access-Control-Max-Age'] = str(max_age)
    hdr['Access-Control-Allow-Credentials'] = str(credentials).lower()
    hdr['Content-Type'] = content_type
    if headers is not None:
        hdr['Access-Control-Allow-Headers'] = headers

    return hdr


def cors(origin=None, methods=None, headers=None, max_age=21600,
         attach_to_all=True, automatic_options=True,
         credentials=False, content_type=None):
    # pylint: disable=R0912
    """Flask decorator to insert CORS headers to the response.

    :param origin:
        This can be ``*`` or a regex, e.g. .*.xxx.com
    """
    if methods is not None:
        methods = ', '.join(sorted(mthd.upper() for mthd in methods))
    if headers is not None and not isinstance(headers, six.string_types):
        headers = ', '.join(hdr.upper() for hdr in headers)
    if not isinstance(origin, six.string_types):
        origin = ', '.join(origin)
    if isinstance(max_age, datetime.timedelta):
        max_age = max_age.total_seconds()

    if credentials and origin == '*':
        raise ValueError('Cannot allow credentials with Origin set to "*"')

    def get_methods():
        """Return allowed methods for CORS response."""
        if methods is not None:
            return methods

        options_resp = flask.current_app.make_default_options_response()
        return options_resp.headers['allow']

    def decorator(func):
        """Function decorator to insert CORS headers."""
        def wrapped_function(*args, **kwargs):
            """Wrapper function to add required headers."""
            if automatic_options and flask.request.method == 'OPTIONS':
                resp = flask.current_app.make_default_options_response()
            else:
                resp = flask.make_response(func(*args, **kwargs))
            if not attach_to_all and flask.request.method != 'OPTIONS':
                return resp

            hdr = resp.headers
            add_hdr = cors_make_headers(base_origin=origin,
                                        max_age=max_age,
                                        credentials=credentials,
                                        content_type=content_type,
                                        methods=get_methods(),
                                        headers=headers)
            for key, val in six.iteritems(add_hdr):
                hdr[key] = val

            return resp

        func.provide_automatic_options = False
        return functools.update_wrapper(wrapped_function, func)

    return decorator


def log_header(header=None):
    # pylint: disable=R0912
    """Flask decorator to log headers or a specific header

    :param header:
        This can be a string as to which header to log
    """
    def decorator(func):
        """Function decorator to log header(s)"""
        def wrapped_function(*args, **kwargs):
            """Wrapper function to add required headers."""
            resp = flask.make_response(func(*args, **kwargs))

            headers = flask.request.headers
            if header is not None:
                _LOGGER.info('header: %s: %r', header, headers.get(header))
                return resp

            _LOGGER.info('headers: %r', headers)
            return resp

        func.provide_automatic_options = False
        return functools.update_wrapper(wrapped_function, func)

    return decorator


def no_cache(func):
    """Decorator to disable proxy response caching."""
    def wrapped_function(*args, **kwargs):
        """Wrapper function to add required headers."""
        if flask.request.method == 'OPTIONS':
            resp = flask.current_app.make_default_options_response()
        else:
            resp = flask.make_response(func(*args, **kwargs))

        hdr = resp.headers
        hdr['Cache-Control'] = 'no-cache, no-store, must-revalidate'

        return resp

    func.provide_automatic_options = False
    return functools.update_wrapper(wrapped_function, func)


def run_wsgi(wsgi_app, port):
    """Runs wsgi (Flask) app using tornado web server."""

    container = tornado.wsgi.WSGIContainer(wsgi_app)
    app = tornado.web.Application([
        (r'.*', tornado.web.FallbackHandler, dict(fallback=container)),
    ])

    http_server = tornado.httpserver.HTTPServer(app)
    http_server.listen(port)
    tornado.ioloop.IOLoop.instance().start()


def run_wsgi_unix(wsgi_app, socket):
    """Runs wsgi (Flask) app using tornado unixsocket web server."""

    container = tornado.wsgi.WSGIContainer(wsgi_app)
    app = tornado.web.Application([
        (r'.*', tornado.web.FallbackHandler, dict(fallback=container)),
    ])

    http_server = tornado.httpserver.HTTPServer(app)
    unix_socket = tornado.netutil.bind_unix_socket(socket)
    http_server.add_socket(unix_socket)
    tornado.ioloop.IOLoop.instance().start()


def raw_get_api(api, cors_handler, marshal=None, resp_model=None,
                parser=None):
    """Returns default API decorator for GET request.

    :param api: Flask rest_plus API
    :param cors_handler: CORS handler
    :param marshal: The API marshaller, e.g. api.marshal_list_with
    :param resp_model: The API response model
    """
    return get_api(
        api, cors_handler,
        marshal=marshal,
        resp_model=resp_model,
        parser=parser,
        json_resp=False,
    )


def get_api(api, cors_handler, marshal=None, resp_model=None,
            parser=None, json_resp=True):
    """Returns default API decorator for GET request.

    :param api: Flask rest_plus API
    :param cors_handler: CORS handler
    :param marshal: The API marshaller, e.g. api.marshal_list_with
    :param resp_model: The API response model
    """
    funcs = [
        cors_handler,
        no_cache,
        log_header(),
    ]

    if json_resp:
        funcs.append(as_json)

    funcs.append(
        api.doc(responses={
            403: 'Not Authorized',
            404: 'Resource does not exist',
        }),
    )

    if parser:
        funcs.insert(-1, api.doc(parser=parser))
    if marshal and resp_model:
        funcs.insert(-1, marshal(resp_model))

    return utils.compose(*funcs)


def _common_api(api, cors_handler, marshal=None, req_model=None,
                resp_model=None, parser=None):
    """Returns default API decorator for common r/w requests.

    :param api: Flask rest_plus API
    :param cors_handler: CORS handler
    :param marshal: The API marshaller, e.g. api.marshal_list_with, this will
        override the default `api.marshal_with()`
    :param req_model: The API request model
    :param resp_model: The API response model
    """
    funcs = [
        cors_handler,
        no_cache,
        log_header(),
        as_json,
        api.doc(responses={
            403: 'Not Authorized',
            404: 'Resource does not exist',
        }),
    ]

    if parser or req_model:
        params = dict()
        if parser:
            params['parser'] = parser
        if req_model:
            params['body'] = req_model

        funcs.insert(-1, api.doc(**params))

    if marshal and resp_model:
        funcs.insert(-1, marshal(resp_model))
    elif resp_model:
        funcs.insert(-1, api.marshal_with(resp_model))

    return utils.compose(*funcs)


def post_api(api, cors_handler, marshal=None, req_model=None, resp_model=None,
             parser=None):
    """Returns default API decorator for POST request."""
    return _common_api(
        api, cors_handler,
        marshal=marshal,
        req_model=req_model,
        resp_model=resp_model,
        parser=parser,
    )


def put_api(api, cors_handler, req_model=None, resp_model=None, parser=None):
    """Returns default API decorator for PUT request."""
    return _common_api(
        api, cors_handler,
        req_model=req_model,
        resp_model=resp_model,
        parser=parser,
    )


def delete_api(api, cors_handler, req_model=None, resp_model=None):
    """Returns default API decorator for DELETE request."""
    return _common_api(
        api, cors_handler,
        req_model=req_model,
        resp_model=resp_model,
    )


def namespace(api, name, description):
    """Return namespace name for the given module."""
    return api.namespace(
        name.split('.')[-1].replace('_', '-'),
        description=description
    )


def wants_json_resp(request):
    """
    Decide whether the response should be in json format based on the request's
    accept header.

    Code taken from: http://flask.pocoo.org/snippets/45/
    """
    best = request.accept_mimetypes.best_match(['application/json',
                                                'text/html'])

    return (
        best == 'application/json' and
        request.accept_mimetypes[best] > request.accept_mimetypes['text/html'])


def opt_gzip(func):
    """Gzip the response if the client accepts it."""
    @functools.wraps(func)
    def decorated_function(*args, **kwargs):
        """Gzip the response if the client accepts it."""
        response = func(*args, **kwargs)
        accept_encodings = flask.request.headers.get('Accept-Encoding', '')

        if 'gzip' not in accept_encodings.lower():
            return response

        uncompressed = response.data
        if not isinstance(response.data, io.IOBase):
            uncompressed = io.BytesIO(response.data)

        compressed = io.BytesIO()
        with gzip.GzipFile(mode='wb', fileobj=compressed) as gz:
            with uncompressed:
                shutil.copyfileobj(uncompressed, gz)

        response.data = compressed.getvalue()
        response.headers['Content-Encoding'] = 'gzip'
        response.headers['Content-Length'] = len(response.data)

        return response

    return decorated_function
