"""Checks ldap infrastructure.
"""

import unittest
import os
import pwd
import time
import logging

from treadmill import admin
from treadmill import checkout as chk
from treadmill import sysinfo


_LOGGER = logging.getLogger(__name__)


def mk_test_cls(sysproid, ldap_suffix, url):
    """Make test class."""

    class LdapTest(unittest.TestCase):
        """LDAP checkout."""

        def setUp(self):
            self.name = '%s.chk.%s.%s' % (sysproid,
                                          sysinfo.hostname(),
                                          time.time())
            manifest = {
                'memory': '1G',
                'cpu': '10%',
                'disk': '1G',
                'services': [
                    {'name': 'test', 'command': 'test'}
                ]
            }

            conn = admin.Admin(url, ldap_suffix)
            conn.connect()

            self.admin_app = admin.Application(conn)
            self.admin_app.create(self.name, manifest)

        def tearDown(self):
            self.admin_app.delete(self.name)

    return LdapTest


def test(ldap_urls, ldap_suffix):
    """Create sysapps test class."""

    sysproid = os.environ.get('TREADMILL_ID', pwd.getpwuid(os.getuid())[0])

    tests = []

    for url in ldap_urls:

        cls = mk_test_cls(sysproid, ldap_suffix, url)

        for other_url in ldap_urls:

            @chk.T(cls, url=url, other_url=other_url, ldap_suffix=ldap_suffix)
            def _test_replication(self, ldap_suffix, url, other_url):
                """Check ldap replication {url} -> {other_url}."""
                print('Checking %s' % url)

                time.sleep(2)

                other_conn = admin.Admin(other_url, ldap_suffix)
                other_conn.connect()
                other_admin_app = admin.Application(other_conn)

                other_admin_app.get(self.name)

        tests.append(cls)

    return tests
