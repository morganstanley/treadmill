"""Trace function invocation using decorator."""


import functools
import logging
import threading


_LOGGER = logging.getLogger(__name__)
_TRACE = threading.local()


def disable(func):
    """Decorator to disable trace on a given function."""
    return _enable_trace(func, False)


def enable(func):
    """Decorator to enable trace on a given function."""
    return _enable_trace(func, True)


def _enable_trace(func, enabled):
    """Returns decorator to enable/disable tracing on the function."""
    @functools.wraps(func)
    def _wrap(*args, **kwargs):
        """Decorator to disable function trace."""
        prev_state = getattr(_TRACE, 'enabled', True)
        _TRACE.enabled = enabled
        try:
            return func(*args, **kwargs)
        finally:
            _TRACE.enabled = prev_state

    return _wrap


def trace_calls(frame, event, arg):
    """Trace calls using sys.settrace."""
    # Ignore line events.
    if event == 'line':
        return

    trace_enabled = getattr(_TRACE, 'enabled', None)
    if trace_enabled is None:
        trace_enabled = True

    if not trace_enabled:
        return

    code = frame.f_code
    func_name = code.co_name
    filename = code.co_filename

    if func_name == 'write':
        # Ignore write() calls from print statements.
        return

    if func_name.startswith('_'):
        # Ignore private functions.
        return

    # Ignore non-treadmill modules.
    if filename.find('/treadmill/') < 0:
        return

    if event == 'call':
        _LOGGER.debug('%s: %s ( %s )', filename, func_name, frame.f_locals)
    elif event == 'return':
        _LOGGER.debug('%s => %s', func_name, arg)
    elif event == 'exception':
        exc_type, exc_value, _traceback = arg
        line_no = frame.f_lineno
        _LOGGER.debug('exception: %s[%s]: %s, %s', filename, line_no,
                      exc_type.__name__, exc_value)
    else:
        # Ignore c_calls/c_return/c_exception.
        pass

    return trace_calls
