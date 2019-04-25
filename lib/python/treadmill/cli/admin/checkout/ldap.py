"""Checkout ldap servers ensemble.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import logging

import click
import ldap3

from treadmill import admin
from treadmill import cli
from treadmill import context

_LOGGER = logging.getLogger(__name__)


def _metadata(total, accuracy):
    """genertate metadata for alerts
    """
    return {
        'index': 'name',
        'query': 'select * from ldap_server_csn',
        'checks': [
            {
                'description': 'LDAP Status',
                'query':
                    """
                    select name, health from ldap_status where health == 0
                    order by name
                    """,
                'metric':
                    """
                    select count(*) as down from ({query})
                    """,
                'alerts': [
                    {
                        'description': 'All LDAP servers are up',
                        'severity': 'error',
                        'threshold': {
                            'down': 1
                        }
                    },
                    {
                        'description': 'LDAP server group is working',
                        'severity': 'critical',
                        'threshold': {
                            'down': total
                        }
                    }
                ]
            },
            {
                'description': 'LDAP ContextCSN',
                'query':
                    """
                    select name, csn_timestamp, csn_id
                    from ldap_server_csn order by csn_id, name
                    """,
                'metric':
                    """
                    select count(*) as async
                    from ldap_server_csn ls, (
                        select max(csn_timestamp) as csn_timestamp,
                        csn_id from ldap_server_csn group by csn_id
                    ) q
                    where ls.csn_id == q.csn_id
                    and (q.csn_timestamp - %d) > (ls.csn_timestamp + 0)
                    """ % accuracy,
                'alerts': [
                    {
                        'description': 'LDAP servers are synchronized',
                        'severity': 'critical',
                        'threshold': {
                            'async': 1
                        }
                    }
                ]
            },
            {
                'description': 'LDAP schema',
                'query':
                    """
                    select name, schema
                    from ldap_schema order by name
                    """,
                'metric':
                    """
                    select count(*) as total
                    from (
                        select distinct(schema) from ldap_schema
                    )
                    """,
                'alerts': [
                    {
                        'description': 'LDAP schemas are synchronized',
                        'severity': 'critical',
                        'threshold': {
                            'total': 2
                        }
                    }
                ]
            }
        ]  # end of 'checks'
    }


def init():
    """Top level command handler."""

    @click.command('ldap')
    @click.option('--ldap-list', required=True,
                  envvar='TREADMILL_LDAP_LIST', type=cli.LIST)
    @click.option('--accuracy', required=False, type=int, default=200,
                  help=(
                      'allow slight inconsistent CSN timestamp in centisecond.'
                      'Default: 200 centi-second'
                  ))
    def check_ldap_servers(ldap_list, accuracy):
        """Check ldap server status."""

        def _check(conn, **_kwargs):
            """LDAP Server state: """
            ldap_suffix = context.GLOBAL.ldap_suffix

            conn.execute(
                """
                CREATE TABLE ldap_server_csn (
                    name text,
                    csn_timestamp integer,
                    csn_id text
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE ldap_status (
                    name text,
                    health integer
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE ldap_schema (
                    name text,
                    schema text
                )
                """
            )

            rows = []
            status = []
            schemas = []
            # we fetch contextCSN of each ldap server to check consistency
            for ldap_url in ldap_list:
                # pylint: disable=protected-access
                ldap_conn = admin._ldap.Admin([ldap_url], ldap_suffix)
                try:
                    ldap_conn.connect()
                    context_csn = ldap_conn.get(
                        dn='dc=ms,dc=com',
                        query='(objectclass=*)',
                        attrs=ldap3.ALL_OPERATIONAL_ATTRIBUTES
                    )['contextCSN']
                    _LOGGER.debug(
                        'Raw contextCSN: %s => %r', ldap_url, context_csn
                    )
                    schema = ldap_conn.schema()
                    _LOGGER.debug(
                        'schema: %s => %r', ldap_url, schema
                    )
                    schema_str = json.dumps(schema, sort_keys=True)
                    ldap_conn.close()

                    for csn in context_csn:
                        (csn_timestamp, _, csn_id, _) = csn.split('#')
                        rows.append((ldap_url, csn_timestamp, csn_id))

                    status.append((ldap_url, 1))
                    schemas.append((ldap_url, schema_str))
                except KeyError:
                    # contextCSN may not have been generated in ldap
                    status.append((ldap_url, 0))
                except ldap3.core.exceptions.LDAPBindError:
                    status.append((ldap_url, 0))

            conn.executemany(
                """
                INSERT INTO ldap_server_csn(name, csn_timestamp, csn_id)
                values(?, ?, ?)
                """,
                rows
            )
            conn.executemany(
                'INSERT INTO ldap_status(name, health) values(?, ?)',
                status
            )
            conn.executemany(
                'INSERT INTO ldap_schema(name, schema) values(?, ?)',
                schemas
            )

            return _metadata(len(ldap_list), accuracy)

        return _check

    return check_ldap_servers
