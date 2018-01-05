"""LBControl2 SOAP endpoint connection handling.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import pwd

import suds
import suds.cache
import suds.client
import suds.sax.element
import suds.transport
import urllib_kerberos as urllib_krb

from six.moves import urllib

_LOGGER = logging.getLogger(__name__)

_LBCONTROL_URL = 'webinfra/lbControl/webapp/LbServices'
_LBCONTROL_EP = {
    'DEV': 'lbcontrol.webfarm-dev.ms.com',
    'QA': 'lbcontrol2-qa.ms.com',
    'PROD': 'lbcontrol2-treadmill.ms.com',
}
_WSDL_URL = 'http://{host}/{url}?wsdl'
_KERB2SM_EP = 'http://krb2sm-v2-prod.ms.com/login?grn=grn:/ms/ei/Treadmill'


class _LBTransport(suds.transport.http.HttpTransport):
    """This defines a transport that speaks SPNEGO/SiteMinder."""
    def u2opener(self):
        if self.urlopener is None:
            proxy_kerb_support = urllib_krb.ProxyKerberosAuthHandler()
            proxy_support = urllib.request.ProxyHandler(self.proxy)
            http_support = urllib.request.HTTPHandler()
            kerb_support = urllib_krb.HTTPKerberosAuthHandler()
            cookie_support = urllib.request.HTTPCookieProcessor(self.cookiejar)

            opener = urllib.request.build_opener(http_support,
                                                 proxy_support,
                                                 kerb_support,
                                                 proxy_kerb_support,
                                                 cookie_support)

            # Prime CookieJar with siteminder cookie
            opener.open(_KERB2SM_EP)
            return opener

        else:
            return self.urlopener


def connect(environment, enduser=None):
    """Connect to the LBControl2 SOAP endpoint.

    If env is specified, use that LB environment.
    If enduser is specified, make requests on behalf of that user.
    """
    env = environment.upper()

    wsdl_url = _WSDL_URL.format(
        host=_LBCONTROL_EP[env],
        url=_LBCONTROL_URL
    )

    # Setup the requesting user
    if not enduser:
        enduser = pwd.getpwuid(os.geteuid())[0]

    # Create the client
    enduserns = ('enduser', 'http://myControl/')
    enduserval = suds.sax.element.Element('enduser', ns=enduserns)
    enduserval.setText(enduser)

    _LOGGER.info('connect env: %s, enduser: %s, wsdl_url: %s',
                 environment, enduser, wsdl_url)

    # default cache path is /tmp/suds, which is bad for multi-user environment
    cache = suds.cache.ObjectCache('/tmp/suds-{0}'.format(os.getuid()), days=1)
    return suds.client.Client(
        url=wsdl_url,
        proxy={},
        transport=_LBTransport(),
        soapheaders=enduserval,
        cache=cache
    )
