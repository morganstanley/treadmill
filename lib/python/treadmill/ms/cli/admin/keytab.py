"""Treadmill keytab management.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import base64
import glob
import io
import logging
import os
import re
import shutil
import socket
import tempfile

import click
import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

from treadmill import admin
from treadmill import cli
from treadmill import context
from treadmill import gssapiprotocol
from treadmill import zkutils
from treadmill import zknamespace as z


_LOGGER = logging.getLogger(__name__)


_KT_SPLIT = '/ms/dist/cloud/PROJ/treadmill-tktfwd/1.9/bin/kt-split'

_KT_SPOOL_DIR = '/var/tmp/treadmill_master/*/*/treadmill/spool/keytabs'


def fwd_keytab(host, port, kt_file):
    """Forward keytabs to keytab locker."""

    service = 'host@%s' % host

    _LOGGER.info('connecting: %s:%s, %s', host, port, service)
    client = gssapiprotocol.GSSAPILineClient(host, int(port), service)
    if not client.connect():
        _LOGGER.error('Unable to connect.')
        return

    tmp_dir = tempfile.mkdtemp()
    subprocess.check_call([_KT_SPLIT, '--dir=%s' % tmp_dir, kt_file])

    fqdn = socket.getfqdn()
    hostname = socket.gethostname()

    try:
        for kt_part in glob.glob(os.path.join(tmp_dir, '*')):
            if fqdn in kt_part or hostname in kt_part:
                _LOGGER.info('Ignore host keytab: %s', kt_part)
                continue

            _LOGGER.info('Forwarding: %s', kt_part)
            with io.open(kt_part, 'rb') as f:
                encoded = base64.urlsafe_b64encode(f.read())
                client.write(
                    b' '.join(
                        [
                            b'put',
                            os.path.basename(kt_part).encode(),
                            encoded
                        ]
                    )
                )
                client.read()

    finally:
        _LOGGER.info('Deleting temp directory: %s', tmp_dir)
        shutil.rmtree(tmp_dir)

        _LOGGER.info('Closing connection.')
        client.disconnect()


def fwd_keytab_all(zkclient, kt_file):
    """Forward keytab to the locker(s)."""
    lockers = zkutils.with_retry(zkclient.get_children, z.KEYTAB_LOCKER)
    for locker in lockers:
        host, port = locker.split(':')
        fwd_keytab(host, port, kt_file)


def _hostname2keytab(hostname):
    return 'host#{}@is1.morgan'.format(hostname)


def _keytab2hostname(keytab):
    res = re.match('^host#(.+)@is1.morgan$', keytab)
    if res:
        return res.group(1)


def init():
    """Return top level command handler."""

    @click.group()
    def keytab():
        """Keytab admin commands."""
        pass

    @keytab.command()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.argument('keytab')
    def fwd(keytab):
        """Forward keytab to the cell keytab locker."""
        fwd_keytab_all(context.GLOBAL.zk.conn, keytab)

    @keytab.command()
    def check():
        """Check keytabs."""
        admin_cell = admin.Cell(context.GLOBAL.ldap.conn)

        cells = admin_cell.list({})
        for cell in cells:
            cli.out('===== Checking cell %s =====', cell['_id'])
            try:
                cell_vips = cell['data']['lbvirtual']['vips']
            except KeyError:
                cell_vips = []

            cli.out('* Checking vips')
            vips = {}
            for vip in cell_vips:
                vip = re.sub(r'\.\d+$', '', vip)
                try:
                    hostname, _aliases, _ipaddrs = socket.gethostbyname_ex(vip)
                    vips[vip] = hostname
                    cli.echo_green('[OK] %s: %s', vip, hostname)
                except socket.gaierror as err:
                    cli.echo_red('[ERROR] %s: %s', vip, err)

            for master in cell['masters']:
                cli.out('* Checking %s', master['hostname'])
                process = subprocess.Popen(
                    [
                        'ssh', '-o', 'StrictHostKeyChecking=no',
                        master['hostname'], 'ls', _KT_SPOOL_DIR
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                out, err = process.communicate()
                ret = process.poll()
                if ret != 0:
                    cli.echo_red('[ERROR] %s', err)
                    continue

                keytabs = {
                    kt_file: _keytab2hostname(kt_file)
                    for kt_file in out.split()
                }

                for vip, hostname in vips.items():
                    keytab = _hostname2keytab(hostname)
                    if keytab not in keytabs:
                        cli.echo_red('[ERROR] %s: %s', vip, keytab)
                    else:
                        cli.echo_green('[OK] %s: %s', vip, keytab)

                hostnames = set(vips.values())
                for kt_file, hostname in keytabs.items():
                    if hostname not in hostnames:
                        cli.echo_yellow('[WARNING] extra: %s', kt_file)

    del fwd
    del check

    return keytab
