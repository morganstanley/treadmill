"""DNS Context."""

from __future__ import absolute_import

import logging
import random

from treadmill import dnsutils
from treadmill import context


_LOGGER = logging.getLogger(__name__)


def _resolve_srv(dns_domain, dns_server, srv_rec):
    """Returns list of host, port tuples for given srv record."""
    _LOGGER.debug('Query DNS -t SRV %s.%s', srv_rec, dns_domain)
    if not dns_domain:
        raise context.ContextError('Treadmill DNS domain not specified.')

    result = dnsutils.srv(
        srv_rec + '.' + dns_domain, dns_server
    )
    random.shuffle(result)
    return result


def _srv_to_urls(srv_recs, protocol=None):
    """Randomizes and converts SRV records to URLs."""
    return [dnsutils.srv_rec_to_url(srv_rec,
                                    protocol=protocol)
            for srv_rec in srv_recs]


def _api(ctx, target, proto=None):
    """Resolve cell api."""
    srv_recs = _resolve_srv(ctx.dns_domain, ctx.dns_server, target)
    if not srv_recs:
        raise context.ContextError('No srv records found: %s' % target)

    return _srv_to_urls(srv_recs, proto)


def _cell_api(ctx):
    if not ctx.cell:
        raise context.ContextError('Cell not specified.')
    return _api(ctx, '_http._tcp.cellapi.{}.cell'.format(ctx.cell), 'http')


def _state_api(ctx):
    if not ctx.cell:
        raise context.ContextError('Cell not specified.')
    return _api(ctx, '_http._tcp.stateapi.{}.cell'.format(ctx.cell), 'http')


def _ws_api(ctx):
    if not ctx.cell:
        raise context.ContextError('Cell not specified.')
    return _api(ctx, '_ws._tcp.wsapi.{}.cell'.format(ctx.cell), 'ws')


def _admin_api(ctx):
    """Resolve admin API SRV records."""
    # Default.
    #
    for scope in ctx.get('api_scope', []):
        try:
            result = _api(ctx, '_http._tcp.adminapi.' + scope, 'http')
            if result:
                return result
        except context.ContextError:
            pass

    raise context.ContextError('no admin api found.')


def _zk_url(ctx):
    """Resolve Zookeeper connection string from DNS."""
    if not ctx.dns_domain:
        _LOGGER.warn('DNS domain is not set.')
        zkurl_rec = dnsutils.txt('zk.%s' % (ctx.cell), ctx.dns_server)
    else:
        zkurl_rec = dnsutils.txt(
            'zk.%s.%s' % (ctx.cell, ctx.dns_domain),
            ctx.dns_server
        )

    if zkurl_rec:
        return zkurl_rec[0]
    else:
        return None


def _ldap_url(ctx):
    """Resolve LDAP for given cell."""

    if not ctx.cell:
        raise context.ContextError('Cell not specified.')

    ldap_srv_rec = dnsutils.srv(
        '_ldap._tcp.%s.%s' % (ctx.cell, ctx.dns_domain),
        ctx.dns_server
    )
    url = ','.join(['ldap://%s:%s' % (rec[0], rec[1])
                    for rec in ldap_srv_rec])
    return url


_RESOLVERS = {
    'admin_api': _admin_api,
    'cell_api': _cell_api,
    'state_api': _state_api,
    'ws_api': _ws_api,
    'zk_url': _zk_url,
    'ldap_url': _ldap_url,
}


def resolve(ctx, attr):
    """Resolve attribute from DNS."""
    value = _RESOLVERS[attr](ctx)
    _LOGGER.debug('Resolved from DNS: %s - %s', attr, value)
    return value


def init(_ctx):
    """Init context."""
    pass
