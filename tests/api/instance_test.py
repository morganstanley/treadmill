"""Instance API tests."""

import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock
import yaml

from treadmill import admin
from treadmill import exc
from treadmill import master
from treadmill.api import instance


def _create_apps(_zkclient, _app_id, app, _count):
    return app


class ApiInstanceTest(unittest.TestCase):
    """treadmill.api.instance tests."""

    def setUp(self):
        self.instance = instance.API()

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.context.ZkContext.conn', mock.Mock())
    @mock.patch('treadmill.master.create_apps', mock.Mock())
    def test_normalize_run_once(self):
        """ test missing defaults which cause the app to fail """
        doc = """
        services:
        - command: /bin/sleep 1m
          name: sleep1m
          restart:
            limit: 0
        memory: 150M
        cpu: 10%
        disk: 100M
        """

        master.create_apps.side_effect = _create_apps

        new_doc = self.instance.create("proid.app", yaml.load(doc))

        # Disable E1126: Sequence index is not an int, slice, or instance
        # pylint: disable=E1126
        self.assertEquals(new_doc['services'][0]['restart']['interval'], 60)
        self.assertTrue(master.create_apps.called)

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.context.ZkContext.conn', mock.Mock())
    @mock.patch('treadmill.master.create_apps', mock.Mock())
    def test_run_once_small_memory(self):
        """ testing too small memory definition for container """
        doc = """
        services:
        - command: /bin/sleep 10
          name: sleep1m
          restart:
            limit: 0
        memory: 10M
        cpu: 10%
        disk: 100M
        """

        master.create_apps.side_effect = _create_apps
        with self.assertRaises(exc.TreadmillError):
            self.instance.create("proid.app", yaml.load(doc))

if __name__ == '__main__':
    unittest.main()
