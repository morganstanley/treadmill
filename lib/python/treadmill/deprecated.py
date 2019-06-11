"""Deprecation tools
"""

import functools
import inspect
import warnings


def deprecated(why):
    """This is a decorator which can be used to mark functions
    as deprecated.

    .. code-block:: python

    >>> from treadmill import deprecated
    >>> @deprecated.deprecated('why, something useful')
    ... def deprecated_function(x, y):
    ...     pass
    """

    def decorator(wrapped):
        """Decorate a `wrapped` function.
        """

        if inspect.isclass(wrapped):
            fmt = 'Call to deprecated class {name!r} ({why}).'
        else:
            fmt = 'Call to deprecated function {name!r} ({why}).'
        message = fmt.format(name=wrapped.__name__, why=why)

        @functools.wraps(wrapped)
        def wrapper(*args, **kwargs):
            """Wrapper for deprecated function.
            NOTE: Docstring get replaced by `functools.wraps`.
            """
            warnings.warn(message, category=DeprecationWarning, stacklevel=2)
            return wrapped(*args, **kwargs)

        return wrapper

    return decorator


__all__ = (
    'deprecated',
)
