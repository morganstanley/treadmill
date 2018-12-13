""" plugins for journal """

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc
import logging
import time

import six

_LOGGER = logging.getLogger(__name__)

_STEP_BEGIN = 'begin'
_STEP_END = 'end'
_STEP_ABORT = 'abort'


@six.add_metaclass(abc.ABCMeta)
class BaseJournaler:
    """ abstract journaler class """

    def __init__(self, user_clbk, **_kwargs):
        """ you need to extend this constructor to add more journal export init
        step by using the parameters from kwargs
        """
        self._user_clbk = user_clbk

    def log_begin(self, transaction_id, resource, action, args):
        """ log begin step of the journal before API is called """
        pk = None
        payload = {}

        nargs = len(args)
        if nargs > 0:
            pk = str(args[0])
        if nargs > 1:
            payload = args[1]

        user = self._user_clbk()
        timestamp = self._get_timestamp()

        _LOGGER.debug(
            'Log Journal %s: %s %s %s %s %s', _STEP_BEGIN,
            transaction_id, resource, action, pk, user
        )

        return self._log_exec(_STEP_BEGIN, transaction_id,
                              resource, action, pk, payload, user, timestamp)

    def log_end(self, transaction_id, resource, action, args, result):
        """ log end step of the journal after API is called"""
        pk = None

        nargs = len(args)
        if nargs > 0:
            pk = str(args[0])

        user = self._user_clbk()
        timestamp = self._get_timestamp()

        _LOGGER.debug(
            'Log Journal %s: %s %s %s %s %s', _STEP_END,
            transaction_id, resource, action, pk, user
        )

        return self._log_exec(_STEP_END, transaction_id,
                              resource, action, pk, result, user, timestamp)

    def log_abort(self, transaction_id, resource, action, args, exception):
        """ log abort step of the journal in case API is aborted"""
        pk = None

        nargs = len(args)
        if nargs > 0:
            pk = str(args[0])

        payload = {'error': str(exception)}
        user = self._user_clbk()
        timestamp = self._get_timestamp()

        _LOGGER.debug(
            'Log Journal %s: %s %s %s %s %s', _STEP_ABORT,
            transaction_id, resource, action, pk, user
        )

        return self._log_exec(_STEP_ABORT, transaction_id,
                              resource, action, pk, payload,
                              user, timestamp)

    # pylint: disable=C0103
    @abc.abstractmethod
    def _log_exec(self, step, transaction_id,
                  resource, action, rsrc_id, payload,
                  user, timestamp):
        """This needs to implement due to different backend of journler.
        """

    @staticmethod
    def _get_timestamp():
        """return epoc time in seconds
        returns -- `float`
        """
        return time.time()


class NullJournaler(BaseJournaler):
    """ do nothing for journal """

    def __init__(self):
        super(NullJournaler, self).__init__(lambda: None)

    def _log_exec(self, step, transaction_id,
                  resource, action, rsrc_id, payload,
                  user, timestamp):
        # yes, we want the method do nothing
        pass
