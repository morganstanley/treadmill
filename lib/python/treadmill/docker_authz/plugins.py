"""Treadmill docker authz plugins for different Docker APIs
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import re

_LOGGER = logging.getLogger(__name__)

# to store user attribute in different images in dockerd
_IMAGE_USER = dict()

DEFAULT_ALLOW_MSG = 'Allowed'


class AuthzPlugin:

    """Base class of authz plugin
    """
    # pylint: disable=unused-argument
    def run_req(self, method, url, request):
        """Request Callback
        """
        return (200, DEFAULT_ALLOW_MSG)

    # pylint: disable=unused-argument
    def run_res(self, method, url, request, response):
        """Response Callback
        """
        return (200, DEFAULT_ALLOW_MSG)


class DockerInspectUserPlugin(AuthzPlugin):
    """Check user attribute in images via docker inspect
    """
    # pylint: disable=unused-argument
    def run_res(self, method, url, request, response):
        """cache image users from response body
        """
        match = re.match(r'^/[^/]+/images/(?P<image>.+)/json$', url)
        if method == 'GET' and match:
            image = match.groupdict()['image']
            user = self._get_image_user(response)

            if user:
                _LOGGER.info('Set image %s, user %s', image, user)
                _IMAGE_USER[image] = user
            else:
                _LOGGER.info('No user in image %s', image)

        return (200, DEFAULT_ALLOW_MSG)

    @staticmethod
    def _get_image_user(response):
        """Get potential image user from image metadata
        request example:
            GET /v1.26/containers/<image_name>/json

        response body example:
        ---
        Config:
            User: xxxx
        """
        user = None
        try:
            config = response.get('Config', {})
            user = config.get('User', None)
        # pylint: disable=broad-except
        except Exception as err:
            _LOGGER.error('Failed to get user name: %s', err)

        return user


class DockerRunUserPlugin(AuthzPlugin):
    """Authz plugin to check user for docker run
    """
    def __init__(self, users):
        super(DockerRunUserPlugin, self).__init__()
        self._users = users

    def run_req(self, method, url, request):
        """Check user from request_id
        request example:
            POST /v1.26/containers/create
            ---
            User: xxx
            Image: xxx
            ...
        """
        status = 200
        msg = DEFAULT_ALLOW_MSG

        if method == 'POST' and 'containers/create' in url:
            # User name and image name defined in request body
            container_user = request.get('User', '')
            image = request.get('Image', '')
            if container_user:
                # if user name provide, it is equal to user id of container
                for user in self._users:
                    if container_user == '{}:{}'.format(user[0], user[1]):
                        break
                else:
                    msg = 'user {} not allowed'.format(container_user)
                    status = 403
            else:
                # no user from docker run, we must ensure user defined in image
                if image and image in _IMAGE_USER:
                    msg = 'Run as {} defined in image {}'.format(
                        _IMAGE_USER[image], image
                    )
                else:
                    msg = 'user not provided nor defined in image {}'.format(
                        image
                    )
                    status = 403

        return (status, msg)


class DockerExecUserPlugin(AuthzPlugin):
    """Authz plugin for docker exec
    """
    def __init__(self, users):
        super(DockerExecUserPlugin, self).__init__()
        self._users = users

    def run_req(self, method, url, request):
        """Check user from request_id
        request example:
            POST /v1.26/containers/foo/exec
            ---
            User: xxxx
            ...
        """
        status = 200
        msg = DEFAULT_ALLOW_MSG

        match = re.match(r'^/[^/]+/containers/(?P<container>.+)/exec$', url)
        if method == 'POST' and match:
            # User name and image name defined in request body
            _container = match.groupdict()['container']
            container_user = request.get('User', '')
            if container_user:
                for user in self._users:
                    if container_user == '{}:{}'.format(user[0], user[1]):
                        break
                else:
                    msg = 'user {} not allowed'.format(container_user)
                    status = 403
            else:
                msg = 'Must provide user for exec'
                status = 403

        return (status, msg)
