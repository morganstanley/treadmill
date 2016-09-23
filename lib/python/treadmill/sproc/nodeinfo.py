"""Node info sproc module."""
from __future__ import absolute_import

import errno
import signal

import logging
import os
import socket
import tempfile
import time

import click
import jinja2

from .. import context
from .. import exc
from .. import sysinfo
from .. import utils
from .. import zkutils
from .. import nodeinfo


_LOGGER = logging.getLogger(__name__)

_NGINX_CONF = jinja2.Template("""

daemon off;

events {
}

http {
    server {
        listen {{ port }};
        root {{ root }};

{% for host in hostports %}
        location ~ ^/{{ host }}(/?)(.*) {
            proxy_pass http://{{ host }}/$request_uri;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
{% endfor %}
    }

{% for host, port in hostports.items() %}
    upstream {{ host }} {
       server {{ host }}:{{ port }};
    }
{% endfor %}
}

""")


def hostname_resolves(hostname):
    """Checks if the host resolves to IP or is stale (no longer in DNS)."""
    try:
        socket.gethostbyname(hostname)
        return True
    except socket.error:
        return False


def init():
    """Top level command handler."""

    @click.group(name='nodeinfo')
    def nodeinfo_grp():
        """Manages local node info server and redirector."""
        pass

    @nodeinfo_grp.command()
    @click.option('--pid', help='NGINX pid file', default='/tmp/nginx.pid')
    @click.option('--root', help='NGINX root directory', default='/var/tmp')
    @click.option('--port', help='NGINX port', default=8080, type=int)
    @click.argument('conf', 'NGINX conf file.')
    def redirector(pid, root, port, conf):
        """Runs local nodeinfo redirector."""
        context.GLOBAL.zk.conn.add_listener(zkutils.exit_on_lost)

        @exc.exit_on_unhandled
        def update_config(_event):
            """Watch on nodeinfo nodes, regenerate nginx conf."""
            nodeinfos = context.GLOBAL.zk.conn.get_children(
                '/nodeinfo', watch=update_config)
            hostports = dict([(hostport.split(':')) for hostport in nodeinfos])

            # Filter out hostnames that do not resolve, nginx does not like
            # them.
            hostports = {host: port for (host, port) in hostports.iteritems()
                         if hostname_resolves(host)}

            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(_NGINX_CONF.render(port=port,
                                           root=root,
                                           pid_file=pid,
                                           hostports=hostports))

            os.rename(f.name, conf)

            # read pid file, and reload nginx conf.
            try:
                with open(pid) as pid_file:
                    nginx_pid = int(pid_file.read())
                    _LOGGER.info('reloading nginx pid: %s', nginx_pid)
                    os.kill(nginx_pid, signal.SIGHUP)
            except IOError as err:
                if err.errno == errno.ENOENT:
                    _LOGGER.warn('nginx pid file %s does not exist.', pid)
                else:
                    raise

        update_config(None)

        while True:
            time.sleep(10000)

        _LOGGER.info('service shutdown.')

    @nodeinfo_grp.command()
    @click.option('--port', help='NGINX port', default=0, type=int)
    @click.argument('approot', 'Treadmill approot.')
    def server(port, approot):
        """Runs nodeinfo server."""
        if port == 0:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('0.0.0.0', 0))
            port = sock.getsockname()[1]
            sock.close()

        hostname = sysinfo.hostname()
        hostports = context.GLOBAL.zk.conn.get_children('/nodeinfo')
        # Remove stale info.
        for hostport in hostports:
            host, _ = hostport.split(':')
            if host == hostname:
                _LOGGER.info('Removing old nodeinfo: %s', hostport)
                zkutils.ensure_deleted(context.GLOBAL.zk.conn,
                                       os.path.join('/nodeinfo', hostport))

        zkutils.put(context.GLOBAL.zk.conn,
                    os.path.join('/nodeinfo/%s:%s' % (hostname, port)))
        context.GLOBAL.zk.conn.stop()

        _LOGGER.info('Starting nodeinfo server on port: %s', port)
        utils.drop_privileges()
        nodeinfo.run(approot, port)

    del redirector
    del server

    return nodeinfo_grp
