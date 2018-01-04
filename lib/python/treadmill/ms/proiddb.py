"""ProidDB queries."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sqlite3

_PROID_DB = '//ms/dist/prolog/PROJ/proid/incr/common/etc/proid.v10.db3'


def eonid(proid, cursor=None):
    """Returns eonid given the proid.

    :param proid:
        Proidid to be queried.
    :type proid:
        ``str``
    :returns:
        ``str`` -- eonid of the Proid
    """
    if not cursor:
        cursor = connect()

    cursor.execute(
        '''
        select eonid from proid_eonid
        where name = ?
        ''',
        (proid, )
    )
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        return None


def environment(proid, cursor=None):
    """Returns environment of the proid.

    :param proid:
        Proidid to be queried.
    :type proid:
        ``str``
    :returns:
        ``str`` -- Environment of the Proid
    """
    if not cursor:
        cursor = connect()

    cursor.execute(
        '''
        select environment from proid
        where name = ?
        ''',
        (proid, )
    )
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        return None


def connect(database=_PROID_DB):
    """Open an SQLite connection and return a cursor."""
    conn = sqlite3.connect(database)
    return conn.cursor()


__all__ = [
    'environment',
    'eonid',
    'connect'
]
