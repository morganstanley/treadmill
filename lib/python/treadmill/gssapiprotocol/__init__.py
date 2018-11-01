"""GSSAPI linebased client/server protocol.
#
# Usage:
#
# Server:
#
#     class Echo(GSSAPILineServer):
#         def got_line(self, line):
#             self.write('echo: ' + line)
#
#     class EchoFactory(protocol.Factory):
#         def buildProtocol(self, addr):  # pylint: disable=C0103
#             return Echo()
#
#     def main():
#         reactor.listenTCP(8080, EchoFactory())
#         reactor.run()
#
# Client:
#
#     client = GSSAPILineClient(host, port, service)
#     if client.connect():
#
#         client.write('Hi')
#         print(client.read())
#
#     client.disconnect()
#
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

# This is done for backward compatibility, until all code is refactored to
# explicitly import client or server, whatever is needed.
from .lineserver import GSSAPILineServer
from .lineclient import GSSAPILineClient
from .lineclient import GSSError


__all__ = [
    'GSSAPILineServer',
    'GSSAPILineClient',
    'GSSError',
]
