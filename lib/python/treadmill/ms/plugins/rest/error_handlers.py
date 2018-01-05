"""Plugin for adding external error handlers.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

from six.moves import http_client

from treadmill import osnoop

from treadmill.ms import msdependencies  # pylint: disable=unused-import

if os.name == 'posix':
    from treadmill.ms import lbcontrol
    from treadmill.ms import lbendpoint

_LOGGER = logging.getLogger(__name__)


@osnoop.windows
def init(api):
    """initialize the error_handlers plugin"""
    _LOGGER.info('Loading REST error handlers: %s', __name__)

    @api.errorhandler(lbendpoint.NoVirtualsError)
    def _no_virtual_error(err):
        """NoVirtualsError exception handler."""
        _LOGGER.info('No virtual found error: %r', err)
        return {'message': str(err),
                'status': http_client.BAD_REQUEST}, http_client.BAD_REQUEST

    @api.errorhandler(lbendpoint.NoAvailablePortError)
    def _no_available_port_error(err):
        """NoAvailablePortError exception handler."""
        _LOGGER.info('NoAvailablePortError error: %r', err)
        return {'message': str(err),
                'status': http_client.NOT_FOUND}, http_client.NOT_FOUND

    @api.errorhandler(lbendpoint.PortInUseError)
    def _port_in_use_error(err):
        """PortInUseError exception handler."""
        _LOGGER.info('PortInUseError error: %r', err)
        return {'message': str(err),
                'status': http_client.FOUND}, http_client.FOUND

    @api.errorhandler(lbendpoint.PoolAlreadyExistsError)
    def _pool_already_exists_error(err):
        """PoolAlreadyExistsError exception handler."""
        _LOGGER.info('PoolAlreadyExistsError error: %r', err)
        return {'message': str(err),
                'status': http_client.FOUND}, http_client.FOUND

    @api.errorhandler(lbcontrol.SOAPError)
    def _lbcontrol_soap_error_exc(err):
        """SOAPError error exception handler."""
        _LOGGER.info('SOAPError error: %r', err)
        return {
            'message': err.message,
            'status': http_client.INTERNAL_SERVER_ERROR
        }, http_client.INTERNAL_SERVER_ERROR
