"""Unit test for journal
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

from treadmill import journal
from treadmill.journal import plugin as jplugin


class API:
    """ dummy API to test """

    def __init__(self):

        def get(rsrc_id):
            """ dummy get """
            return {'_id': rsrc_id}

        # pylint: disable=W0613
        def create(rsrc_id, rsrc):
            """ dummy create """
            return {'_id': rsrc_id}

        # pylint: disable=W0613
        def update(rsrc_id, rsrc):
            """ dummy update """
            return {'_id': rsrc_id}

        self.get = get
        self.create = create
        self.update = update


class ListJournaler(jplugin.BaseJournaler):
    """ simplest Journaler implementation """

    def __init__(self, user_clbk):
        super(ListJournaler, self).__init__(user_clbk)
        self.journals = []

    def _log_exec(self, step, transaction_id,
                  resource, action, rsrc_id, payload,
                  user, timestamp):

        self.journals.append(
            (
                '%s,%s,%s,%s,%s,%s,%0.2f' % (
                    step, transaction_id, resource, action,
                    rsrc_id, user, timestamp
                ),
                payload
            )
        )

    @staticmethod
    def _get_timestamp():
        # overwrite of original get timestamp
        return 1.0


def _user_clbk():
    """ dummy user callback """
    return 'treadmill'


class JournalTest(unittest.TestCase):
    """Journal test"""

    def setUp(self):
        api = API()
        self._journaler = ListJournaler(_user_clbk)
        self._api = journal.wrap(api, self._journaler)

    @mock.patch('treadmill.journal._get_tx_id', mock.Mock(return_value='txid'))
    def test_create(self):
        """ test journal by calling create API """
        result = self._api.create('myid', {'hello': 'world'})
        self.assertEqual(result, {'_id': 'myid'})
        self.assertEqual(
            self._journaler.journals,
            [
                ('begin,txid,' + __name__ + ',create,myid,treadmill,1.00',
                 {'hello': 'world'}),
                ('end,txid,' + __name__ + ',create,myid,treadmill,1.00',
                 {'_id': 'myid'})
            ]
        )


if __name__ == '__main__':
    unittest.main()
