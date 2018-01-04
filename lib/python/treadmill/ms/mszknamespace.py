"""MS Specific zk namespace"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from treadmill import zknamespace as z

PRODPERIM = '/prodperim'

# pylint: disable=C0103
path = z.path
path.prodperim = z.make_path_f(PRODPERIM)
