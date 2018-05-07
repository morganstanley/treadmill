"""Unit test for treadmill.cron.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

import treadmill
from treadmill import restclient
from treadmill.cron import model as cron_model
from treadmill.cron.run import app as cron_app


class CronTest(unittest.TestCase):
    """Tests for teadmill.cron."""

    @mock.patch('treadmill.cron.model.app.create', mock.Mock())
    def test_cron_create(self):
        """Tests cron job create.
        """
        scheduler = mock.MagicMock()
        cron_model.create(
            scheduler, '1', 'app:create', 'app', 'cron-expression', 3
        )
        treadmill.cron.model.app.create.assert_called_with(
            scheduler, '1', 'app', 'create', 'app', 'cron-expression', 3
        )

    @mock.patch('treadmill.restclient.get', mock.Mock())
    @mock.patch('treadmill.restclient.post', mock.Mock())
    def test_cron_stop_bad(self):
        """Tests cron job stop, no instances.
        """
        resp_mock = mock.Mock()
        resp_mock.json.return_value = {'instances': []}
        treadmill.restclient.get.return_value = resp_mock

        cron_app.stop(job_id='foo.bar-stop', app_name='foo.bar')

        restclient.post.assert_not_called()

    @mock.patch('treadmill.restclient.get', mock.Mock())
    @mock.patch('treadmill.restclient.post', mock.Mock())
    def test_cron_stop_good(self):
        """Tests cron job stop, with instances.
        """
        resp_mock = mock.Mock()
        resp_mock.json.return_value = {'instances': ['foo.bar#123456789']}
        treadmill.restclient.get.return_value = resp_mock

        cron_app.stop(job_id='foo.bar-stop', app_name='foo.bar')

        restclient.post.assert_called_once_with(
            ['http+unix://%2Ftmp%2Fcellapi.sock'], '/instance/_bulk/delete',
            headers={u'X-Treadmill-Trusted-Agent': u'cron'},
            payload=dict(instances=[u'foo.bar#123456789'])
        )


if __name__ == '__main__':
    unittest.main()
