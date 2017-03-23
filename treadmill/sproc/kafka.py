"""Treadmill Kafka system process"""


import sys

import logging
import os
import pwd

import click
import kazoo
import jinja2

import treadmill

# pylint: disable=E0611
from treadmill import admin
from treadmill import cli
from treadmill import context
from treadmill import kafka as tkafka
from treadmill import subproc
from treadmill import sysinfo
from treadmill import zkutils


BROKER_PROP_FILE_NAME = 'broker.properties'

DEFAULT_KAFKA_LAUNCHER = 'kafka_server_start'
DEFAULT_KAFKA_TEMPLATE_DIR = os.path.join(treadmill.TREADMILL, 'etc', 'kafka')

DEFAULT_KAFKA_PROPERTIES = os.path.join(treadmill.TREADMILL, 'etc', 'kafka',
                                        BROKER_PROP_FILE_NAME)

HOSTNAME = sysinfo.hostname()
CURRENT_USER = pwd.getpwuid(os.getuid()).pw_name

_LOGGER = logging.getLogger(__name__)


def setup_kafka_env(zkurl, template_dir, broker_port, broker_id, zkroot,
                    krb_realm):
    """Setup the Kafka environment within the container"""
    zk_servers = tkafka.zk_instances_by_zkurl(zkurl, zkroot)
    _LOGGER.debug('zk_servers: %s', zk_servers)

    loader = jinja2.FileSystemLoader(template_dir)
    template_env = jinja2.Environment(loader=loader)

    broker_props_name = 'broker.properties'
    broker_props = os.path.join(tkafka.DEFAULT_KAFKA_DIR, broker_props_name)
    _LOGGER.info('Writting %s file', broker_props)

    with open(broker_props, 'w') as prop_fh:
        variables = {
            'broker_port': str(broker_port),
            'broker_id': str(broker_id),
            'zk_servers': zk_servers,
            'user_id': CURRENT_USER,
        }
        broker_template = template_env.get_template(broker_props_name)
        broker_txt = broker_template.render(variables)
        prop_fh.write(broker_txt)

    jaas_conf_name = 'jaas.conf'
    jaas_conf = os.path.join(tkafka.DEFAULT_KAFKA_DIR, jaas_conf_name)
    _LOGGER.info('Writting %s file', jaas_conf)

    with open(jaas_conf, 'w') as jaas_fh:
        variables = {
            'user_id': CURRENT_USER,
            'hostname': HOSTNAME,
            'krb_realm': krb_realm,
        }
        jaas_template = template_env.get_template(jaas_conf_name)
        jaas_txt = jaas_template.render(variables)
        jaas_fh.write(jaas_txt)

    return (broker_props, jaas_conf)


def make_sasl_acl(perm, krb_realm):
    """Create SASL ACL"""
    scheme = 'sasl'
    principal = '{}/{}@{}'
    host_principal = principal.format(CURRENT_USER, HOSTNAME, krb_realm)

    acls = [kazoo.security.make_acl(scheme, host_principal,
                                    read='r' in perm,
                                    write='w' in perm,
                                    create='c' in perm,
                                    delete='d' in perm,
                                    admin='a' in perm)]

    admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
    cell = admin_cell.get(context.GLOBAL.cell)

    for master in cell['masters']:
        host_principal = principal.format(
            CURRENT_USER, master['hostname'], krb_realm)

        acls.append(
            kazoo.security.make_acl(scheme, host_principal,
                                    read='r' in perm,
                                    write='w' in perm,
                                    create='c' in perm,
                                    delete='d' in perm,
                                    admin='a' in perm)
        )

    return acls


def setup_kafka_in_zk(zkroot, krb_realm):
    """Setup /kafka in this cell's Zookeeper servers"""
    # For now we are using a non-kerberized Kafka instance and thus needs
    # world writable node, unfortunately...
    zkclient = context.GLOBAL.zk.conn
    _LOGGER.info('Ensuring %s exists', zkroot)
    zkclient.ensure_path(zkroot)

    _LOGGER.info('Setting world readable and SASL ACL on %s', zkroot)
    sasl_acls = make_sasl_acl('cdrwa', krb_realm)
    acls = [
        zkutils.make_anonymous_acl('r'),
        zkutils.make_user_acl(CURRENT_USER, 'cdrwa'),
    ]
    acls.extend(sasl_acls)

    zkclient.set_acls(zkroot, acls)


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--kafka-dir', help='The Kafka dir to instal in',
                  default=tkafka.DEFAULT_KAFKA_DIR)
    @click.option('--broker-port', help='The Kafka broker port',
                  type=int, envvar='TREADMILL_ENDPOINT_CLIENT',
                  required=True)
    @click.option('--broker-id', help='The Kafka broker ID',
                  type=int, envvar='TREADMILL_IDENTITY',
                  required=True)
    @click.option('--launcher',
                  help='Kafka launcher name, see etc/linux.exe.config',
                  default=DEFAULT_KAFKA_LAUNCHER)
    @click.option('--template-dir', help='Kafka template dir',
                  default=DEFAULT_KAFKA_TEMPLATE_DIR)
    @click.option('--java-home', help='Value of JAVA_HOME',
                  envvar='JAVA_HOME')
    @click.option('--zkroot', help='The ZK root to use',
                  default=tkafka.KAFKA_ZK_ROOT)
    @click.option('--env-vars', help='Environment vars to pass to Kafka',
                  type=cli.LIST, default='')
    @click.option('--krb-realm', help='Kerberos domain',
                  required=True)
    @click.argument('opts', nargs=-1)
    def kafka(kafka_dir, broker_port, broker_id, launcher, template_dir,
              java_home, zkroot, env_vars, krb_realm, opts):
        """Run Treadmill Kafka"""
        _LOGGER.debug('broker_port: %s', broker_port)
        _LOGGER.info('Setting up Kafka ZK root %s, if necessary', zkroot)
        setup_kafka_in_zk(zkroot, krb_realm)
        setup_kafka_in_zk('/'.join((zkroot, 'brokers')), krb_realm)

        kafka_env = tkafka.setup_env(kafka_dir=kafka_dir, with_data_dir=True,
                                     server=True)
        kafka_env['JAVA_HOME'] = java_home
        os.environ['JAVA_HOME'] = java_home

        _LOGGER.debug('kafka_env: %r', kafka_env)

        zkurl = context.GLOBAL.zk.url
        _LOGGER.debug('zkurl: %r', zkurl)

        (broker_props, jaas_conf) = setup_kafka_env(
            zkurl, template_dir, broker_port, broker_id, zkroot, krb_realm
        )

        kafka_opts = (
            '-Djava.security.auth.login.config={}'
            ' -Dzookeeper.sasl.client.username={}'.format(
                jaas_conf, CURRENT_USER)
        )

        kafka_env['KAFKA_OPTS'] = kafka_opts
        os.environ['KAFKA_OPTS'] = kafka_opts

        for env_var in env_vars:
            if os.environ.get(env_var):
                kafka_env[env_var] = os.environ[env_var]

        cmd = [launcher, broker_props]

        if opts:
            cmd.extend(opts)

        rc = subproc.check_call(cmd, environ=kafka_env)

        sys.exit(rc)

    return kafka
