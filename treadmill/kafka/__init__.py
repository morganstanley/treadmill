"""Treadmill Kafka API"""

import logging
import os
import re
import socket

from .. import admin as tadmin
from .. import context
from .. import dnsutils
from .. import discovery
from .. import fs

_LOGGER = logging.getLogger(__name__)

KAFKA_ZK_ROOT = 'kafka'
DEFAULT_KAFKA_DIR = '/var/tmp/kafka'

RUN_CLASS_SCRIPT_NAME = 'kafka_run_class'

KAFKA_APP_PATTERN = '*.kafka.*'
DEFAULT_BROKER_ENDPOINT_NAME = 'client'


def setup_env(kafka_dir=DEFAULT_KAFKA_DIR, with_data_dir=False, server=False):
    """Setup the Kafka environemtn, like log and data directories.

    :param kafka_dir: an optional Kafka directory, default is
        kafka.DEFAULT_KAFKA_DIR
    :type kafka_dir: string

    :param data_dir: setup the data directory too, defaul is False
    :type data_dir: bool
    """

    kafka_env = {
        'APP_LOG': app_log(kafka_dir),
    }

    if os.environ.get('JAVA_HOME') is not None:
        kafka_env['JAVA_HOME'] = os.environ.get('JAVA_HOME')

    kafka_log_dir = log_dir(kafka_dir)
    kafka_env['LOG_DIR'] = kafka_log_dir

    fs.mkdir_safe(kafka_log_dir)

    if with_data_dir:
        datadir = data_dir(kafka_dir)
        fs.mkdir_safe(datadir)
        kafka_env['DATA_DIR'] = datadir

    if server:
        kafka_env['USE64BITJVM'] = '1'
        kafka_env['KAFKA_HEAP_OPTS'] = '-Xmx4G -Xms4G'
        kafka_env['JVM_ARGUMENTS'] = (
            '-XX:+UnlockCommercialFeatures '
            '-XX:+FlightRecorder -agentlib:'
            'jdwp=transport=dt_socket,'
            'server=y,address=8011,suspend=n'
        )

    return kafka_env


def log_dir(kafka_dir=DEFAULT_KAFKA_DIR):
    """Get the Kafka log directory

    :param kafka_dir: an optional Kafka directory, default is
        kafka.DEFAULT_KAFKA_DIR
    :type kafka_dir: string
    """
    return os.path.join(kafka_dir, 'logs')


def app_log(kafka_dir=DEFAULT_KAFKA_DIR):
    """Get Kafka log file, full path.

    :param kafka_dir: an optional Kafka directory, default is
        kafka.DEFAULT_KAFKA_DIR
    :type kafka_dir: string
    """
    return os.path.join(kafka_dir, 'log', 'kafka.log')


def data_dir(kafka_dir=DEFAULT_KAFKA_DIR):
    """Get the Kafka data directory

    :param kafka_dir: an optional Kafka directory, default is
        kafka.DEFAULT_KAFKA_DIR
    :type kafka_dir: string
    """
    return os.path.join(kafka_dir, 'data')


def zk_instances_by_zkurl(zkurl, zkroot=KAFKA_ZK_ROOT):
    """Get the Zookeeper instances suitable for Kafka by ZK URL

    :param zkurl: the Zookeeper URL
    :type zkurl: string

    :param zkroot: the Zookeeper chroot for this Kafka
    :type zkroot: string
    """
    zk_servers = os.path.join(
        re.sub(r'^.*[@]', '', zkurl), zkroot
    )
    _LOGGER.debug('zk_servers: %s', zk_servers)

    return zk_servers


def get_replica(brokers):
    """Get the number of replicas, essentially this is len(get_brokers())

    See kafka.get_brokers() for more details on the arguments
    """
    replica = 0
    for broker in brokers:
        if _is_broker_up(broker):
            replica = replica + 1

    return replica


def run_class_script():
    """Get the Kafka run class"""
    return RUN_CLASS_SCRIPT_NAME


def _get_kafka_endpoint(zkclient, app_pattern, endpoint, watcher_cb=None):
    """Get the Kafka client endpoint host and cell

    :param zkclient: a zkclient
    :type zkclient: kazoo.client

    :param app_pattern: the Kafka broker app pattern, e.g. treadmlp.kafka-*
    :type app_pattern: string

    :param endpoint: the Kafka broker client endpoint name in the app, default
        is DEFAULT_BROKER_ENDPOINT_NAME
    :type endpoint: string
    """
    app_discovery = discovery.Discovery(zkclient, app_pattern, endpoint)
    if watcher_cb:
        endpoints = app_discovery.get_endpoints_zk(watch_cb=watcher_cb)
    else:
        endpoints = app_discovery.get_endpoints()

    return endpoints


def _is_broker_up(hostport):
    """Test whether a broker is up"""
    try:
        host, port = hostport.split(':')
        timeout = 3
        socket.create_connection((host, port), timeout)
        return True
    except socket.error:
        pass
    return False


def get_brokers(cellname, domain, zkclient, app_pattern=None,
                endpoint=DEFAULT_BROKER_ENDPOINT_NAME,
                watcher_cb=None):
    """Get the Kafka broker host and ports for the supplied cell

    :param cellname: a cell
    :type cellname: str

    :param domain: Treadmill DNS domain
    :type domain: str

    :param zkclient: a ZZookeeper client
    :type zkclient: kazoo.client

    :param app_pattern: the Kafka broker app pattern, e.g. treadmlp.kafka.*
    :type app_pattern: string

    :param endpoint: the Kafka broker client endpoint name in the app, default
        is DEFAULT_BROKER_ENDPOINT_NAME
    :type endpoint: string

    :param watcher_cb: ZK watcher callback; if the endpoints change, call this.
        Only valid if you set both app_pattern and endpoint
    :type watcher_cb: func
    """
    brokers = get_master_brokers(cellname, domain)

    if brokers:
        for hostport in brokers:
            # if at least one broker is up, then we are good; the reason for
            # this is that we could have DNS records setup but no Kafka broker
            # servers running on the hosts.
            if _is_broker_up(hostport):
                return brokers

    brokers = []
    admin_cell = tadmin.Cell(context.GLOBAL.ldap.conn)
    cell = admin_cell.get(cellname)
    for master in cell.get('masters', []):
        port = master.get('kafka-client-port')
        if port is None:
            continue
        hostport = '{0}:{1}'.format(master['hostname'], port)
        brokers.append(hostport)

    if brokers:
        return brokers

    if app_pattern:
        # TODO: pylint complains about:
        #                Redefinition of brokers type from list to set
        # pylint: disable=R0204
        brokers = _get_kafka_endpoint(zkclient, app_pattern, endpoint,
                                      watcher_cb=watcher_cb)

    if brokers:
        return brokers

    admin_app = tadmin.Application(context.GLOBAL.ldap.conn)
    matched_apps = admin_app.list({'_id': KAFKA_APP_PATTERN})
    _LOGGER.debug('matched_apps: %r', matched_apps)

    kafka_apps = [app['_id'] for app in matched_apps]

    for app in kafka_apps:
        kbrokers = _get_kafka_endpoint(zkclient, app, endpoint)
        if kbrokers:
            brokers.extend(kbrokers)

    return brokers


def get_master_brokers(cell, domain):
    """Get the masker Kafka brokers

    :param cell: a cell
    :type cell: str

    :param broker_id: a specific broker id, else, all brokers are returned
    :type broker_id: int

    :returns: a list of host:ports
    """
    label = '_kafka._tcp.{0}.{1}'.format(cell, domain)
    return ['{0}:{1}'.format(host, port)
            for (host, port, _prio, _weight) in dnsutils.srv(label)]
