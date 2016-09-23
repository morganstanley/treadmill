"""Treadmill Kafka system process"""
from __future__ import absolute_import

import sys

import logging
import os
import shutil

import click

import treadmill

# pylint: disable=E0611
from .. import context
from .. import kafka as tkafka
from .. import subproc
from .. import zkutils


BROKER_PROP_FILE_NAME = 'broker.properties'

DEFAULT_KAFKA_LAUNCHER = 'kafka_server_start'
DEFAULT_KAFKA_PROPERTIES = os.path.join(treadmill.TREADMILL, 'etc', 'kafka',
                                        BROKER_PROP_FILE_NAME)

_LOGGER = logging.getLogger(__name__)


def setup_kafka_env(zkurl, properties, broker_port, broker_id, zkroot):
    """Setup the Kafka environment within the container"""
    zk_servers = tkafka.zk_instances_by_zkurl(zkurl, zkroot)
    _LOGGER.debug('zk_servers: %s', zk_servers)

    broker_props = os.path.join(tkafka.DEFAULT_KAFKA_DIR, 'broker.properties')

    shutil.copy2(properties, broker_props)

    _LOGGER.info('Adding port and broker.id props to %s', broker_props)
    with open(broker_props, 'a') as prop_fh:
        prop_fh.write('='.join(('port', str(broker_port))) + '\n')
        prop_fh.write('='.join(('broker.id', str(broker_id))) + '\n')
        prop_fh.write('='.join(('zookeeper.connect', zk_servers)) + '\n')

    return broker_props


def setup_kafka_in_zk(zkroot):
    """Setup /kafka in this cell's Zookeeper servers"""
    # For now we are using a non-kerberized Kafka instance and thus needs
    # world writable node, unfortunately...
    zkclient = context.GLOBAL.zk.conn
    zkclient.ensure_path(zkroot)
    zkclient.set_acls(zkroot, [zkutils.make_anonymous_acl('cdrwa')])


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--kafka-dir', help='The Kafka dir to instal in',
                  default=tkafka.DEFAULT_KAFKA_DIR)
    @click.option('--broker-port', help='The Kafka broker port',
                  type=int, envvar='TREADMILL_ENDPOINT_CLIENT',
                  required=True)
    @click.option('--broker-id', help='The Kafka broker ID',
                  type=int, required=True)
    @click.option('--launcher',
                  help='Kafka launcher name, see etc/linux.exe.config',
                  default=DEFAULT_KAFKA_LAUNCHER)
    @click.option('--properties', help='Template Kafka properties file',
                  default=DEFAULT_KAFKA_PROPERTIES)
    @click.option('--java-home', help='Value of JAVA_HOME',
                  envvar='JAVA_HOME')
    @click.option('--zkroot', help='The ZK root to use',
                  default=tkafka.KAFKA_ZK_ROOT)
    @click.argument('opts', nargs=-1)
    def kafka(kafka_dir, broker_port, broker_id, launcher, properties,
              java_home, zkroot, opts):
        """Run Treadmill Kafka"""
        zkurl = context.GLOBAL.zk.url

        _LOGGER.debug('broker_port: %s', broker_port)

        _LOGGER.info('Setting up Kafka ZK root %s, if necessary', zkroot)
        setup_kafka_in_zk(zkroot)

        kafka_env = tkafka.setup_env(kafka_dir=kafka_dir, with_data_dir=True,
                                     server=True)
        kafka_env['JAVA_HOME'] = java_home
        os.environ['JAVA_HOME'] = java_home
        _LOGGER.debug('kafka_env: %r', kafka_env)

        broker_props = setup_kafka_env(zkurl, properties,
                                       broker_port, broker_id, zkroot)

        cmd = [launcher, broker_props]

        if opts:
            cmd.extend(opts)

        rc = subproc.check_call(cmd, environ=kafka_env)

        sys.exit(rc)

    return kafka
