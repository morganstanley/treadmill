"""Plugin for adding external error handlers
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


def init(api):
    """initialize the error_handlers plugin.

    @api.errorhandler(<MyError>)
    def _my_error(err):
        return {'message': str(err),
                'status': http.client.BAD_REQUEST}, http.client.BAD_REQUEST
    """
    del api
