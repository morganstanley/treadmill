"""DNS Context.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import random

from treadmill import dnsutils
from treadmill import context


_LOGGER = logging.getLogger(__name__)


def _resolve_srv(dns_domain, dns_server, srv_rec):
    """Returns randomized list of host, port tuples for given srv record.
    """
    _LOGGER.debug('Query DNS -t SRV %s.%s', srv_rec, dns_domain)
    if not dns_domain:
        raise context.ContextError('Treadmill DNS domain not specified.')

    result = dnsutils.srv(
        srv_rec + '.' + dns_domain, dns_server
    )
    random.shuffle(result)
    return result


def _srv_to_urls(srv_recs, protocol=None):
    """Converts list of SRV records to list of URLs.
    """
    return [dnsutils.srv_rec_to_url(srv_rec,
                                    protocol=protocol)
            for srv_rec in srv_recs]


def _api(ctx, target, proto=None):
    """Resolve cell api."""
    srv_recs = _resolve_srv(ctx.dns_domain, ctx.dns_server, target)
    if not srv_recs:
        raise context.ContextError('No srv records found: %s' % target)

    return (srv_recs, proto)


def _cell_api(ctx, scope=None):
    if scope is None:
        if not ctx.cell:
            raise context.ContextError('Cell not specified.')
        scope = cell_scope(ctx.cell)
    return _api(
        ctx,
        '_http._tcp.cellapi.{scope}'.format(scope=scope),
        'http'
    )


def _state_api(ctx, scope=None):
    if scope is None:
        if not ctx.cell:
            raise context.ContextError('Cell not specified.')
        scope = cell_scope(ctx.cell)
    return _api(
        ctx,
        '_http._tcp.stateapi.{scope}'.format(scope=scope),
        'http'
    )


def _ws_api(ctx, scope=None):
    if scope is None:
        if not ctx.cell:
            raise context.ContextError('Cell not specified.')
        scope = cell_scope(ctx.cell)
    return _api(
        ctx,
        '_ws._tcp.wsapi.{scope}'.format(scope=scope),
        'ws'
    )


def _admin_api(ctx, scope=None):
    """Resolve admin API SRV records."""
    # Default.
    #
    def _lookup(ctx, scope):
        if scope == 'global':
            return _api(ctx, '_http._tcp.adminapi', 'http')
        else:
            return _api(
                ctx,
                '_http._tcp.adminapi.{scope}'.format(scope=scope),
                'http'
            )

    if scope is not None:
        return _lookup(ctx, scope)

    else:
        scopes = ctx.get('api_scope', [])
        if 'global' not in scopes:
            scopes.append('global')

        for api_scope in scopes:
            try:
                result = _lookup(ctx, api_scope)
                if result:
                    return result
            except context.ContextError:
                pass

        raise context.ContextError('no admin api found.')


def _zk_url(ctx):
    """Resolve Zookeeper connection string from DNS."""
    if not ctx.dns_domain:
        _LOGGER.warning('DNS domain is not set.')
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
    return _srv_to_urls(ldap_srv_rec, 'ldap')


_RESOLVERS = {
    'admin_api': lambda ctx: _srv_to_urls(*_admin_api(ctx)),
    'cell_api': lambda ctx: _srv_to_urls(*_cell_api(ctx)),
    'ldap_url': _ldap_url,
    'state_api': lambda ctx: _srv_to_urls(*_state_api(ctx)),
    'ws_api': lambda ctx: _srv_to_urls(*_ws_api(ctx)),
    'zk_url': _zk_url,
}


def resolve(ctx, attr):
    """URL Resolve attribute from DNS.
    """
    url = _RESOLVERS[attr](ctx)
    _LOGGER.debug('Resolved from DNS: %s - %s', attr, url)
    return url


_APILOOKUPS = {
    'admin_api': _admin_api,
    'cell_api': _cell_api,
    'state_api': _state_api,
    'ws_api': _ws_api,
}


def lookup(ctx, attr, scope=None):
    """Do a srv lookup in DNS.
    """
    value = _APILOOKUPS[attr](ctx, scope=scope)
    _LOGGER.debug('API SRV Lookedup from DNS: %s - %r', attr, value)
    return value


def cell_scope(cell):
    """Returns a cell's scope (subdomain) in DNS.
    """
    return '{cell}.cell'.format(cell=cell)


def init(_ctx):
    """Init context.
    """
