"""Treadmill dependencies.

This file containes only open source dependencies. All internal dependencies
are in msdependencies.py
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys
import os

import ms.version

ms.version.addpkg('aniso8601', '0.92')
ms.version.addpkg('apscheduler', '3.3.1')
ms.version.addpkg('backports_abc', '0.5')
ms.version.addpkg('backports.ssl_match_hostname', '3.5.0.1')
ms.version.addpkg('blinker', '1.3')
ms.version.addpkg('certifi', '2017.4.17')
ms.version.addpkg('chardet', '3.0.2')
ms.version.addpkg('click', '6.6')
ms.version.addpkg('colorama', '0.3.2')
ms.version.addpkg('constantly', '15.1.0')
ms.version.addpkg('daemon', '1.6')
ms.version.addpkg('dateutil', '2.5.2')
ms.version.addpkg('decorator', '4.0.2')
ms.version.addpkg('dnspython', '1.15.0')
ms.version.addpkg('docker', '2.4.2')
ms.version.addpkg('docker-pycreds', '0.2.1')
ms.version.addpkg('flask', '0.12.2')
ms.version.addpkg('flask-restful', '0.3.2')
ms.version.addpkg('flask-restplus', '0.10.1')
ms.version.addpkg('funcsigs', '1.0.2')
ms.version.addpkg('futures', '3.1.1')
ms.version.addpkg('gevent', '1.1.1')
ms.version.addpkg('gitdb2', '2.0.2')
ms.version.addpkg('GitPython', '2.1.5')
ms.version.addpkg('greenlet', '0.4.9')
ms.version.addpkg('htmltestrunner', '0.8.0')
ms.version.addpkg('idna', '2.5')
ms.version.addpkg('incremental', '16.10.1')
ms.version.addpkg('ipaddr', '2.1.11')
ms.version.addpkg('ipaddress', '1.0.18')
ms.version.addpkg('iscpy', '1.05')
ms.version.addpkg('itsdangerous', '0.22')
ms.version.addpkg('jinja2', '2.9.5')
ms.version.addpkg('jsonpointer', '1.4')
ms.version.addpkg('jsonschema', '2.5.0')
ms.version.addpkg('kafka-python', '1.0.1')
ms.version.addpkg('kazoo', '2.2.1-ms2')
ms.version.addpkg('ldap3', '2.3')
ms.version.addpkg('lockfile', '0.12.2')
ms.version.addpkg('markupsafe', '0.23-ms1')
ms.version.addpkg('mock', '2.0.0')
ms.version.addpkg('netifaces', '0.10.4-ms1')
ms.version.addpkg('numpy', '1.13.1')
ms.version.addpkg('OpenSSL', '0.15.1')
ms.version.addpkg('pandas', '0.19.2')
ms.version.addpkg('parse', '1.8.0')
ms.version.addpkg('pbr', '3.1.1')
ms.version.addpkg('prettytable', '0.7.2')
ms.version.addpkg('protobuf', '3.0.0b2')
ms.version.addpkg('psutil', '4.2.0')
ms.version.addpkg('pyasn1', '0.1.9')
ms.version.addpkg('python-snappy', '0.5-ms1')
ms.version.addpkg('pytz', '2014.10')
ms.version.addpkg('pywin32', '220')
ms.version.addpkg('requests', '2.18.1')
ms.version.addpkg('requests-kerberos', '0.11.0')
ms.version.addpkg('requests-unixsocket', '0.1.5')
ms.version.addpkg('setuptools', '36.2.7')
ms.version.addpkg('simplejson', '3.8.2')
ms.version.addpkg('singledispatch', '3.4.0.3')
ms.version.addpkg('six', '1.10.0')
ms.version.addpkg('smmap', '0.8.3')
ms.version.addpkg('smmap2', '2.0.3')
ms.version.addpkg('suds', '0.6')
ms.version.addpkg('tabulate', '0.7.7')
ms.version.addpkg('termcolor', '1.1.0')
ms.version.addpkg('tornado', '4.4.2')
ms.version.addpkg('twisted', '17.1.0')
ms.version.addpkg('tzlocal', '1.2')
ms.version.addpkg('urllib3', '1.21.1')
ms.version.addpkg('urllib-kerberos', '0.2.0')
ms.version.addpkg('websocket-client', '0.40.0')
ms.version.addpkg('werkzeug', '0.12.2')
ms.version.addpkg('xlrd', '1.0.0')
ms.version.addpkg('yaml', '3.11')
ms.version.addpkg('zake', '0.0.14')
ms.version.addpkg('zope.interface', '4.4.0')

# These dependencies are Py3 backports only needed with Py2
if sys.version_info[0] < 3:
    ms.version.addpkg('enum34', '1.0')
    ms.version.addpkg('functools32', '3.2.3-1')
    ms.version.addpkg('subprocess32', '3.2.7')

if os.name == 'nt':
    ms.version.addpkg('winkerberos', '0.6.0')
    if sys.version_info[0] < 3:
        ms.version.addpkg('wxPython', '3.0.2')
    # Disable F0401: unable to import 'winkerberos'
    # Disable C0413: Wrong import order
    import winkerberos  # pylint: disable=F0401,C0413
    sys.modules['kerberos'] = winkerberos

else:
    if sys.version_info[0] < 3:
        ms.version.addpkg('kerberos', '1.1.5-ms2')
    else:
        ms.version.addpkg('kerberos', '1.2.5')
    ms.version.addpkg('webauthd_wsgi', '2.0.12', meta='laf')
