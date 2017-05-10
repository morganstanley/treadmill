"""Treadmill Kafka admin API

This module is responsible for administrating topics in Treadmill's Kafka
instances. This includes the following:

    - Get a list of all topics
    - Creating topics, with their partitons and replicas
    - Updating topics
    - Deleting topics
"""


import logging

from .. import context
from .. import kafka
from .. import subproc


_LOGGER = logging.getLogger(__name__)

TOPIC_CLASS = 'kafka.admin.TopicCommand'
ZOOKEEPER_URL_START = 'zookeeper://'


def list_topics(cell):
    """Get a list of all Kafka topics"""
    cell = context.GLOBAL.cell
    context.GLOBAL.resolve(cell)
    zkclient = context.GLOBAL.zk.conn

    topics_path = '/%s/brokers/topics' % kafka.KAFKA_ZK_ROOT
    topics = zkclient.get_children(topics_path)

    return topics


def create_topic(zkurl, topic, partitions, replica=None, kafka_env=None):
    """Create a topic in Kafka instances from zkurl list

    :param zkurl: Zookeeper URL or Zookeeper Kafka instance string, either one
        will work
    :type zkurl: str

    :param topic: the Kafka topic to create
    :type topic: str

    :param partitions: the number of partitions to creatte in the Kafka topic
    :type partitions: int

    :param replica: the number of replicas, defaults to the number of Kafka
        brokers
    :type replica: int
    """
    return _exec_topic_cmd(TOPIC_CLASS, 'create', zkurl, topic,
                           partitions, replica=replica, kafka_env=kafka_env)


def update_topic(zkurl, topic, partitions, replica=None, kafka_env=None):
    """Alter a topic in Kafka instances from zkurl list"""
    return _exec_topic_cmd(TOPIC_CLASS, 'alter', zkurl, topic,
                           partitions, replica=replica, kafka_env=kafka_env)


def delete_topic(zkurl, topic, kafka_env=None):
    """Delete a topic in Kafka instances from zkurl list"""
    return _exec_topic_cmd(TOPIC_CLASS, 'delete', zkurl, topic,
                           kafka_env=kafka_env)


def _exec_topic_cmd(kafka_class, cmd_type, zkurl, topic, partitions=None,
                    replica=None, kafka_env=None):
    """Execute Kafka topic command"""
    if kafka_env is None:
        kafka_env = kafka.setup_env()

    run_class_script = kafka.run_class_script()

    zk_instances = zkurl
    if zkurl.startswith(ZOOKEEPER_URL_START):
        zk_instances = kafka.zk_instances_by_zkurl(zkurl)

    cmd = [run_class_script, kafka_class, '--zookeeper', zk_instances,
           '--topic', topic]

    if cmd_type is not None:
        cmd.append('--%s' % cmd_type)

    if partitions is not None:
        cmd.extend(['--partitions', str(partitions)])

    if replica is not None:
        cmd.extend(['--replication-factor', str(replica)])

    _LOGGER.info('Executing command \'%s\'', ' '.join(cmd))
    rc = subproc.check_call(cmd, environ=kafka_env)

    return rc
