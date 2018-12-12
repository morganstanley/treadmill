"""Treadmill docker authz plugins for different Docker APIs
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import re

_LOGGER = logging.getLogger(__name__)

DEFAULT_ALLOW_MSG = 'Allowed'


class NotAllowedError(Exception):
    """General not allowed excpetion for plugins.
    """


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


class DockerRunPrivilegePlugin(AuthzPlugin):
    """Authz plugin to check run as privileged container
    """

    def __init__(self, privileged=False, caps=None):
        """parameter to allow privileged container and add capablity
        it could be used in the future
        """
        self._privileged = privileged
        self._caps = set() if caps is None else set(caps)

    def run_req(self, method, url, request, **kwargs):
        """Check user from request_id
        request example:
            POST /v1.26/containers/create
            ---
            Privileged: true
            CapAdd: ["SYS_ADMIN"]
            ...
        """
        allow = True
        msg = DEFAULT_ALLOW_MSG

        if method == 'POST' and 'containers/create' in url:
            # if privileged not allowed and run as privileged
            host_config = request.get('HostConfig', {})
            privileged = host_config.get('Privileged', False)
            if privileged and not self._privileged:
                msg = 'Privileged container not allowed'
                allow = False

            # normalize cap_add as set
            cap_add = host_config.get('CapAdd', None)
            cap_add = set() if cap_add is None else set(cap_add)

            # if cap added and not in allowed caps, we deny the request
            if cap_add and not cap_add <= self._caps:
                msg = 'Capacity {} not allowed'.format(cap_add - self._caps)
                allow = False

        return (allow, msg)


class DockerRunUserPlugin(AuthzPlugin):
    """Authz plugin to check user for docker run
    """
    def run_req(self, method, url, request, **kwargs):
        """Check user from request_id
        request example:
            POST /v1.26/containers/create
            ---
            User: xxx
            Image: xxx
            ...
        """
        allow = True
        msg = DEFAULT_ALLOW_MSG

        if method == 'POST' and 'containers/create' in url:
            # User name and image name defined in request body
            run_user = request.get('User', '')
            image = request.get('Image', '')
            # run_user provided by 'docker run --user USER'
            if run_user:
                msg = 'Run image {} as user {}'.format(image, run_user)
            else:
                # no user from docker run
                msg = 'User not provided to run image {}'.format(image)

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
        allow = True
        msg = DEFAULT_ALLOW_MSG

        match = re.match(r'^/[^/]+/containers/(?P<container>.+)/exec$', url)
        if method == 'POST' and match:
            # User name and image name defined in request body
            container = match.groupdict()['container']
            container_user = request.get('User', '')
            if container_user:
                msg = 'Execute as user {} in container {}'.format(
                    container_user, container
                )
            else:
                msg = 'User not provide to execute in continer {}'.format(
                    container
                )

        return (allow, msg)
