"""Treadmill MS dependencies.

This file containes only internal MS dependencies.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import ms.version

ms.version.addpkg('ms.modulecmd', '1.0.5-ms2')
ms.version.addpkg('ms.netkrb', '1.1.0')
ms.version.addpkg('pgelite', '2.7.6', meta='pge')
ms.version.addpkg('pyzmq', '16.0.2')
ms.version.addpkg('flatbuffers', '2015.12.22.1')
ms.version.addpkg('treadmill-watchtower', '2017.10.22-1', meta='cloud')

# TODO: Webauthd_wsgi should be here in msdependencies but it causes issues
#       when added from there.
#
# ms.version.addpkg('webauthd_wsgi', '2.0.11', meta='laf')
