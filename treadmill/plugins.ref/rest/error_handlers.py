"""Plugin for adding external error handlers
"""


def init(api):
    """initialize the error_handlers plugin.

    @api.errorhandler(<MyError>)
    def _my_error(err):
        return {'message': str(err),
                'status': http.client.BAD_REQUEST}, http.client.BAD_REQUEST
    """
    del api
