"""Flask method decorators and other web utilities."""


import datetime
import functools
import logging
import json
import re
import flask

try:
    # pylint: disable=F0401
    import tornado
    from tornado import wsgi
except ImportError:
    # Ignore import errors on RHEL5, as tornado is available only for RHEL6
    pass

# Disable E0611: No 'name' in module
from . import utils  # pylint: disable=E0611

_LOGGER = logging.getLogger(__name__)


def add_dependencies():
    """Load (imports) flask dependencies."""
    pass


def as_json(func):
    """Marshalls function output as json."""
    @functools.wraps(func)
    def decorated_function(*args, **kwargs):
        """Marshalls function output as json."""
        return json.dumps(func(*args, **kwargs))

    return decorated_function


def jsonp(func):
    """Wraps JSONified output for JSONP"""
    @functools.wraps(func)
    def decorated_function(*args, **kwargs):
        """Wraps JSONified output for JSONP"""
        callback = flask.request.args.get('callback', False)
        if callback:
            content = '%s(%s)' % (str(callback),
                                  func(*args, **kwargs).get_data(as_text=True))
            return flask.current_app.response_class(
                content, mimetype='application/json')
        else:
            return func(*args, **kwargs)
    return decorated_function


def cors_domain_match(base_domain):
    """Backward compatability, where * is used to respond to all"""
    if base_domain == '*':
        return base_domain

    origin_re = re.compile(r'https?://%s' % base_domain)

    key = 'HTTP_ORIGIN'
    if key not in flask.request.environ.keys():
        return None

    origin = flask.request.environ[key]
    if origin and origin_re.match(origin):
        return origin
    else:
        return None


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
    if headers is not None and not isinstance(headers, str):
        headers = ', '.join(hdr.upper() for hdr in headers)
    if not isinstance(origin, str):
        origin = ', '.join(origin)
    if isinstance(max_age, datetime.timedelta):
        max_age = max_age.total_seconds()

    if credentials and origin == '*':
        raise ValueError("Cannot allow credentials with Origin set to '*'")

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

            hdr['Access-Control-Allow-Origin'] = cors_domain_match(origin)
            hdr['Access-Control-Allow-Methods'] = get_methods()
            hdr['Access-Control-Max-Age'] = str(max_age)
            hdr['Access-Control-Allow-Credentials'] = str(credentials).lower()
            hdr['Content-Type'] = content_type
            if headers is not None:
                hdr['Access-Control-Allow-Headers'] = headers
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

    container = wsgi.WSGIContainer(wsgi_app)
    app = tornado.web.Application([
        (r".*", tornado.web.FallbackHandler, dict(fallback=container)),
    ])
    app.listen(port)
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


def put_api(api, cors_handler, req_model=None, resp_model=None):
    """Returns default API decorator for PUT request."""
    return _common_api(
        api, cors_handler,
        req_model=req_model,
        resp_model=resp_model,
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
