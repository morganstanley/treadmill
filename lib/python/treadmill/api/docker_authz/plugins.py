"""Treadmill docker authz plugins for different Docker APIs
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import re

from treadmill import utils

_LOGGER = logging.getLogger(__name__)

# to store user attribute in different images in dockerd
_IMAGE_USER = dict()

DEFAULT_ALLOW_MSG = 'Allowed'


class NotAllowedError(Exception):
    """General not allowed excpetion for plugins
    """
    pass


def _norm(user):
    """Convert user name to uid:gid
    """
    if ':' not in user:
        (uid, gid) = utils.get_uid_gid(user)
        return '{}:{}'.format(uid, gid)
    else:
        return user


class AuthzPlugin:

    """Base class of authz plugin
    """
    # pylint: disable=unused-argument
    def run_req(self, method, url, request, **kwargs):
        """Request Callback
        """
        return (True, DEFAULT_ALLOW_MSG)

    # pylint: disable=unused-argument
    def run_res(self, method, url, request, response, **kwargs):
        """Response Callback
        """
        return (True, DEFAULT_ALLOW_MSG)


class DockerInspectUserPlugin(AuthzPlugin):
    """Check user attribute in images via docker inspect
    """
    # pylint: disable=unused-argument
    def run_res(self, method, url, request, response, **kwargs):
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

        return (True, DEFAULT_ALLOW_MSG)

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

    @staticmethod
    def _get_image_user(image):
        if image and image in _IMAGE_USER:
            return _IMAGE_USER[image]
        else:
            return None

    @staticmethod
    def _user_in_whitelist(container_user, whitelist):
        """check container user in whitelist
        """
        # if user not found, _norm will raise KeyError
        container_user = _norm(container_user)

        for user in whitelist:
            if container_user == '{}:{}'.format(user[0], user[1]):
                return

        raise NotAllowedError()

    def run_req(self, method, url, request, **kwargs):
        """Check user from request_id
        request example:
            POST /v1.26/containers/create
            ---
            User: xxx
            Image: xxx
            ...
        """
        users = kwargs.get('users', [])
        allow = True
        msg = DEFAULT_ALLOW_MSG

        if method == 'POST' and 'containers/create' in url:
            # User name and image name defined in request body
            run_user = request.get('User', '')
            image = request.get('Image', '')
            # run_user provided by 'docker run --user USER'
            if run_user:
                image_user = self._get_image_user(image)

                # first check if docker user equals to image user
                # if it is, we directly allow it
                if image_user is None or image_user != run_user:

                    # now check if docker user same as treadmill container user
                    try:
                        self._user_in_whitelist(run_user, users)
                    except NotAllowedError:
                        msg = 'user {} not allowed'.format(run_user)
                        allow = False
                    except KeyError:
                        msg = 'Can not get uid for {}'.format(run_user)
                        allow = False
                else:
                    _LOGGER.info(
                        'user %s same as defined in image', image_user
                    )
            else:
                # no user from docker run, we must ensure user defined in image
                image_user = self._get_image_user(image)
                if image_user is not None:
                    msg = 'Run as {} defined in image {}'.format(
                        image_user, image
                    )
                else:
                    msg = 'user not provided nor defined in image {}'.format(
                        image
                    )
                    allow = False

        return (allow, msg)


class DockerExecUserPlugin(AuthzPlugin):
    """Authz plugin for docker exec
    """
    def run_req(self, method, url, request, **kwargs):
        """Check user from request_id
        request example:
            POST /v1.26/containers/foo/exec
            ---
            User: xxxx
            ...
        """
        users = kwargs.get('users', [])
        allow = True
        msg = DEFAULT_ALLOW_MSG

        match = re.match(r'^/[^/]+/containers/(?P<container>.+)/exec$', url)
        if method == 'POST' and match:
            # User name and image name defined in request body
            _container = match.groupdict()['container']
            container_user = request.get('User', '')
            if container_user:
                for user in users:
                    if container_user == '{}:{}'.format(user[0], user[1]):
                        break
                else:
                    msg = 'user {} not allowed'.format(container_user)
                    allow = False
            else:
                msg = 'Must provide user for exec'
                allow = False

        return (allow, msg)
