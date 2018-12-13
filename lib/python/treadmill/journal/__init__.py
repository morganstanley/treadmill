"""Journal for Treadmill API."""

from __future__ import absolute_import

import logging
import uuid

import decorator

_LOGGER = logging.getLogger(__name__)


class JournalError(Exception):
    """Journal exception class.
    """


def _get_tx_id():
    return str(uuid.uuid4())


def _journal(journaler):
    """Journaler to decorate API functions.
    """

    @decorator.decorator
    def decorated(func, *args, **kwargs):
        """Decorated function."""
        action = getattr(
            func, 'journal_action', func.__name__.strip('_'))
        resource = getattr(
            func, 'journal_resource', func.__module__.strip('_'))

        transaction_id = _get_tx_id()
        journaler.log_begin(transaction_id, resource, action, args)
        try:
            result = func(*args, **kwargs)
            journaler.log_end(transaction_id, resource, action, args, result)
        except Exception as err:
            # we log execption of API and raise again
            journaler.log_abort(transaction_id, resource, action, args, err)
            raise err

        return result

    return decorated


def wrap(api, journaler):
    """Returns module API wrapped with journal function."""
    for action in dir(api):
        if action.startswith('_'):
            continue

        if journaler:
            decorated_journal = _journal(journaler)
            attr = getattr(api, action)
            if hasattr(attr, '__call__'):
                setattr(api, action, decorated_journal(attr))
            elif hasattr(attr, '__init__'):
                setattr(api, action, wrap(attr, journaler))
            else:
                _LOGGER.warning('unknown attribute type: %r, %s', api, action)

    return api
