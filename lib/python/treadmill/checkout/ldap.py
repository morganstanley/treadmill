"""Checks ldap infrastructure.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import os
import pwd
import time
import logging

from treadmill import admin
from treadmill import checkout as chk
from treadmill import sysinfo

_PROVIDER = 'provider='

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


def _get_repl_urls(url):
    """Get all the replication servers in config"""
    ldap_admin = admin.Admin(url, '')
    ldap_admin.connect()

    repls = ldap_admin.get_repls()
    _LOGGER.debug('repls: %r', repls)

    repl_urls = set()
    for repl in repls:
        _rid, url, _rest = repl.split(' ', 2)

        if url.startswith(_PROVIDER):
            url = url[len(_PROVIDER):]
        _LOGGER.debug('url: %r', url)

        repl_urls.add(url)

    return list(repl_urls)


def test(ldap_urls, ldap_suffix):
    """Create sysapps test class."""

    sysproid = os.environ.get('TREADMILL_ID', pwd.getpwuid(os.getuid())[0])

    tests = []

    repl_urls = _get_repl_urls(ldap_urls[0])
    _LOGGER.info('repl_urls: %r', repl_urls)

    for url in repl_urls:

        cls = mk_test_cls(sysproid, ldap_suffix, url)

        for other_url in repl_urls:

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
