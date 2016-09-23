"""Treadmill test application.

There are three independent components:

 - http server (Flask), handlers are added to test various scenarios.
 - tcp echo server.
 - udp echo server.
"""

import logging
import socket

import ms.version  # pylint: disable=E0611,F0401

ms.version.addpkg('OpenSSL', '0.7a2')
ms.version.addpkg('flask', '0.10.1')
ms.version.addpkg('greenlet', '0.3.1')
ms.version.addpkg('itsdangerous', '0.22')
ms.version.addpkg('jinja2', '2.7')
ms.version.addpkg('markupsafe', '0.18')
ms.version.addpkg('setuptools', '14.0')
ms.version.addpkg('werkzeug', '0.9.2')

import flask

from treadmill import sysinfo

_LOGGER = logging.getLogger(__name__)

_WS = flask.Flask(__name__)


@_WS.route('/')
def root():
    """Root handler."""
    mem = sysinfo.mem_info()
    return flask.jsonify({
        'hostname': sysinfo.hostname(),
        'cpu': sysinfo.cpu_count(),
        'memory': mem.total,
    })


@_WS.route('/tcp_echo/<host>/<port>/<message>')
def tcp_echo(host, port, message):
    """Pings tcp server running on host:port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, int(port)))
        sock.send(message)
        reply = sock.recv(1024)
        sock.close()
        return flask.jsonify({'data': str(reply).strip()})
    except socket.error, err:
        sock.close()
        return flask.jsonify({'data', None, 'error', err})


@_WS.route('/tcp_connect/<host>/<port>')
def tcp_connect(host, port):
    """Connects to host:port and wait for reply.

    This function is used to simulate connection to external resource (e.g
    database).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, int(port)))
        reply = sock.recv(1024)
        sock.close()
        return flask.jsonify({'data': str(reply).strip()})
    except socket.error, err:
        sock.close()
        return flask.jsonify({'data', None, 'error', err})


def run_http_server(port):
    """Runs the test app."""
    _WS.run(host='0.0.0.0', port=port)


def run_udp_server(port):
    """Runs udp echo server."""
    address = ('0.0.0.0', port)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(address)

    fqdn = socket.getfqdn()
    _LOGGER.info('Started udp listener on port %s', port)

    while True:
        data, addr = server_socket.recvfrom(2048)
        _LOGGER.info('recv: %r %r', addr, data)
        server_socket.sendto(fqdn + ':' + str(port), addr)


def run_tcp_server(port):
    """Runs tcp echo server."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('0.0.0.0', port))
    sock.listen(1)

    while True:
        conn, addr = sock.accept()
        _LOGGER.info('Connection from: %s', addr)
        while True:
            data = conn.recv(1024)
            if data:
                conn.send(data)
            else:
                conn.close()
                break
