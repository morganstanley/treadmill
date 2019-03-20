"""Runs Treadmill keytab locker service.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import time

import click

from treadmill import appenv
from treadmill import context
from treadmill import endpoints
from treadmill import keytabs
from treadmill import sysinfo
from treadmill import zknamespace as z
from treadmill import zkutils


_LOGGER = logging.getLogger(__name__)


def create_endpoint_file(approot, port, appname, endpoint):
    """Create and link local endpoint file"""
    hostport = '%s:%s' % (sysinfo.hostname(), port)
    zkclinet = context.GLOBAL.zk.conn

    endpoint_proid_path = z.path.endpoint_proid(appname)
    acl = zkclinet.make_servers_acl()
    _LOGGER.info(
        'Ensuring %s exists with ACL %r',
        endpoint_proid_path,
        acl
    )
    zkutils.ensure_exists(
        zkclinet,
        endpoint_proid_path,
        acl=[acl]
    )

    endpoint_path = z.path.endpoint(appname, 'tcp', endpoint)
    _LOGGER.info('Registering %s %s', endpoint_path, hostport)

    # Need to delete/create endpoints for the disovery to pick it up in
    # case of master restart.
    zkutils.ensure_deleted(zkclinet, endpoint_path)
    time.sleep(5)
    zkutils.put(zkclinet, endpoint_path, hostport)

    tm_env = appenv.AppEnvironment(approot)
    endpoints_mgr = endpoints.EndpointsMgr(tm_env.endpoints_dir)
    endpoints_mgr.unlink_all(
        appname=appname,
        endpoint=endpoint,
        proto='tcp'
    )
    endpoints_mgr.create_spec(
        appname=appname,
        endpoint=endpoint,
        proto='tcp',
        real_port=port,
        pid=os.getpid(),
        port=port,
        owner='/proc/{}'.format(os.getpid()),
    )


def init():
    """Top level command handler."""

    @click.group()
    def top():
        """Manage Kerberos keytabs.
        """

    @top.command()
    @click.option('--kt-spool-dir',
                  help='Keytab spool directory.')
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('--port', help='Keytab locker server port.', default=0)
    @click.option('--appname', help='Pseudo app name to use for discovery',
                  required=True)
    @click.option('--endpoint', help='Pseudo endpoint to use for discovery',
                  default='keytabs')
    def locker(kt_spool_dir, approot, port, appname, endpoint):
        """Run keytab locker daemon."""
        kt_locker = keytabs.KeytabLocker(context.GLOBAL.zk.conn, kt_spool_dir)
        kt_server = keytabs.get_listening_server(kt_locker, port)

        port = kt_server.get_actual_port()
        kt_locker.register_endpoint(port)

        create_endpoint_file(approot, port, appname, endpoint)

        _LOGGER.info('Starting keytab locker server on port: %s', port)
        kt_server.run()

    del locker
    return top
