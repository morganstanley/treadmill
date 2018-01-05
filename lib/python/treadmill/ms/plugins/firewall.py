"""Provide exception firewall rules.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

from treadmill import appcfg
from treadmill import iptables
from treadmill import services

_LOGGER = logging.getLogger(__name__)

PRODPERIM_EXCEPTION_SERVICE = 'prodperim_exception_svc'


def _svc_client(tm_env, container_dir):
    """Prodperim exception rule service client."""
    svc = services.ResourceService(
        service_dir=os.path.join(tm_env.root, 'prodperim_exception_svc'),
        impl='treadmill.ms.services.'
             'prodperim_exception_service.'
             'ProdperimExceptionResourceService',
    )
    return svc.make_client(
        os.path.join(container_dir, 'resources', 'prodperim_exception')
    )


def apply_exception_rules(tm_env, container_dir, app):
    """Apply exception firewall rules for app."""
    svc_client = _svc_client(tm_env, container_dir)
    unique_name = appcfg.app_unique_name(app)
    svc_client.put(unique_name, {})
    reply = svc_client.wait(unique_name)
    if reply.get('ipset', None):
        _LOGGER.info(
            'Adding %s to exception rule ipset %s for %s',
            app.network.vip, reply['ipset'], app.proid
        )
        iptables.add_ip_set(reply['ipset'], app.network.vip)
    else:
        _LOGGER.info(
            'No exception rule for %s', app.proid
        )


def cleanup_exception_rules(tm_env, container_dir, app):
    """Clean up exception firewall rules for app."""
    svc_client = _svc_client(tm_env, container_dir)
    unique_name = appcfg.app_unique_name(app)
    try:
        reply = svc_client.get(unique_name)
        if reply is not None and 'ipset' in reply:
            _LOGGER.info(
                'Removing %s from exception rule ipset %s for %s',
                app.network.vip, reply['ipset'], app.proid
            )
            iptables.rm_ip_set(reply['ipset'], app.network.vip)
        else:
            _LOGGER.info(
                'No exception rule for %s', app.proid
            )
    except services.ResourceServiceError:
        pass
    svc_client.delete(unique_name)
