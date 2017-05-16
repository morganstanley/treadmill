"""Trace treadmill application events."""
from __future__ import absolute_import

import functools
import logging
import urllib

import click

from treadmill import context
from treadmill import cli
from treadmill import restclient
from treadmill.websocket import client as wsc
from treadmill.apptrace import events

_LOGGER = logging.getLogger(__name__)


def _find_endpoints(pattern, proto, endpoint, api=None):
    """Return all the matching endpoints in the cell.

    The return value is a dict with host-endpoint assigments as key-value
    pairs.
    """
    apis = context.GLOBAL.state_api(api)

    url = '/endpoint/{}/{}/{}'.format(pattern, proto, endpoint)
    response = restclient.get(apis, url)

    endpoints = response.json()
    if not endpoints:
        cli.bad_exit("Nodeinfo API couldn't be found")

    return endpoints


def _filter_by_uniq(in_=None, out_=None, uniq=None):
    """Only keep the events that belong to the 'uniq' in params."""
    event = events.AppTraceEvent.from_dict(in_['event'])

    if event is None:
        return True

    if uniq is not None and getattr(event, 'uniqueid', None) != uniq:
        return True

    out_.append(event)
    return True


def _get_instance_trace(instance, uniq, ws_api=None):
    """Get the history of the given instance/uniq."""
    rv = []
    message = {'topic': '/trace', 'filter': instance, 'snapshot': True}
    on_message = functools.partial(_filter_by_uniq, out_=rv, uniq=uniq)

    wsc.ws_loop(ws_api, message, True, on_message)

    return rv


def _find_uniq_instance(instance, uniq, ws_api=None):
    if uniq == 'running':
        uniq = None

    history = _get_instance_trace(instance, uniq, ws_api)
    _LOGGER.debug('Instance %s/%s trace: %s', instance, uniq, history)

    if not history:
        return {}

    def get_timestamp(obj):
        """Get the timestamp attribute of the object."""
        return getattr(obj, 'timestamp', None)

    last = max(history, key=get_timestamp)
    _LOGGER.debug("Instance %s's last trace item: %s", instance, last)
    return {'instanceid': last.instanceid,
            'host': getattr(last, 'source', None),
            'uniq': getattr(last, 'uniqueid', None)}


def _instance_to_host(in_=None, out_=None):
    """Update out_ so it contains 'instance: host' as key: value pairs."""
    if 'host' not in in_:
        return True

    out_.update({'instanceid': in_['name'],
                 'host': in_['host'],
                 'uniq': 'running'})
    return False


def _find_running_instance(app, ws_api=None):
    """Find the instance name(s) and host(s) corresponding to the app pattern.
    """
    rv = {}
    message = {'topic': '/endpoints',
               'filter': app,
               'proto': 'tcp',
               'endpoint': 'ssh',
               'snapshot': True}

    on_message = functools.partial(_instance_to_host, out_=rv)

    wsc.ws_loop(ws_api, message, True, on_message)

    return rv


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--api',
                  envvar='TREADMILL_STATEAPI',
                  help='State API url to use.',
                  metavar='URL',
                  required=False)
    @click.argument('app')
    @click.option('--cell',
                  callback=cli.handle_context_opt,
                  envvar='TREADMILL_CELL',
                  expose_value=False,
                  required=True)
    @click.option('--host',
                  help='Hostname where to look for the logs',
                  required=False)
    @click.option('--service',
                  help='The name of the service for which the logs are '
                       'to be retreived',
                  required=False)
    @click.option('--sys',
                  help='The name of the system component for which the logs '
                       'are to be retrieved',
                  required=False)
    @click.option('--uniq',
                  default='running',
                  help="The container id. Specify this if you look for a "
                       "not-running (terminated) application's log",
                  required=False)
    @click.option('--ws-api',
                  help='Websocket API url to use.',
                  metavar='URL',
                  required=False)
    def logs(api, app, host, service, sys, uniq, ws_api):
        """View application logs."""
        logtype = 'service' if service else 'sys'

        logname = service or sys
        if logname is None:
            cli.bad_exit("Please specify either the 'service' or 'sys'"
                         "parameter.")

        if host is None:
            instance = None
            if uniq == 'running':
                instance = _find_running_instance(app, ws_api)

            if not instance:
                instance = _find_uniq_instance(app, uniq, ws_api)

            if not instance:
                cli.bad_exit('No {}instance could be found.'.format(
                    'running ' if uniq == 'running' else ''))

            _LOGGER.debug('Found instance: %s', instance)

            host = instance['host']
            uniq = instance['uniq']

        try:
            endpoint, = [ep
                         for ep in _find_endpoints(
                             urllib.quote('root.*'), 'tcp', 'nodeinfo', api)
                         if ep['host'] == host]
        except ValueError as err:
            _LOGGER.exception(err)
            cli.bad_exit('No endpoint found on %s', host)

        api = 'http://{0}:{1}'.format(endpoint['host'], endpoint['port'])
        logurl = '/app/%s/%s/%s/%s' % (urllib.quote(app),
                                       urllib.quote(uniq),
                                       logtype,
                                       urllib.quote(logname))

        log = restclient.get(api, logurl)
        click.echo(log.text)

    return logs
