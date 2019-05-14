"""keytab2 module
"""

import base64
import io
import logging

from treadmill import exc
from treadmill import fs

_LOGGER = logging.getLogger(__name__)

# sqlite3 table name for tracking relationships between VIP keytab and proid
TABLE = 'keytab_proid'


class KeytabClientError(Exception):
    """Treadmill keytab client error
    """


class KeytabLockerError(exc.TreadmillError):
    """Treadmill keytab locker operation error.
    """

    __slots__ = ()


def read_keytab(keytab_file):
    """get encoded data from keytab file
    """
    _LOGGER.debug('Reading keytab file %s', keytab_file)
    with io.open(keytab_file, 'rb') as f:
        encoded = base64.urlsafe_b64encode(f.read()).decode()
        return encoded


def write_keytab(keytab_file, encoded):
    """Safely writes encoded keytab data to file.
    We get encoded keytab from via json gssapiprotocol
    and decode into real keytab in files

    :param fname: Keytab filename.
    :param encoded: Keytab encoded data
    """
    _LOGGER.debug('Write keytab file %s', keytab_file)
    fs.write_safe(
        keytab_file,
        lambda f: f.write(base64.urlsafe_b64decode(encoded)),
        prefix='.tmp',
        mode='wb'
    )
