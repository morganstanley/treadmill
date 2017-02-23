"""Plugin for adding external error handlers"""
from __future__ import absolute_import


def init(api):
    """initialize the error_handlers plugin.

    @api.errorhandler(<MyError>)
    def _my_error(err):
        return {'message': str(err),
                'status': httplib.BAD_REQUEST}, httplib.BAD_REQUEST
    """
    del api
