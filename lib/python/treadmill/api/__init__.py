"""API package.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import six

from treadmill import authz as authz_mod
from treadmill.journal import plugin as jplugin
from treadmill import journal


def _empty(value):
    """Check if value is empty and need to be removed."""
    return (value is None or
            value is False or
            value == {} or
            value == [])


def normalize(rsrc):
    """Returns normalized representation of the resource.

       - all null attributes are removed recursively.
       - all null array members are remove.
    """
    if isinstance(rsrc, dict):
        return normalize_dict(rsrc)
    elif isinstance(rsrc, list):
        return normalize_list(rsrc)
    else:
        return rsrc


def normalize_dict(rsrc):
    """Normalize dict."""
    norm = {
        key: value
        for key, value in six.iteritems(rsrc)
        if not _empty(value)
    }
    for key, value in six.iteritems(norm):
        norm[key] = normalize(value)
    return norm


def normalize_list(rsrc):
    """Normalize list."""
    return [
        normalize(item)
        for item in rsrc
        if not _empty(item)
    ]


class Context:
    """API context."""

    def __init__(self, authorizer=None, journaler=None):
        self.authorizer = (authz_mod.NullAuthorizer()
                           if authorizer is None else authorizer)
        self.journaler = (jplugin.NullJournaler()
                          if journaler is None else journaler)

    def build_api(self, api_cls, kwargs=None):
        """ build api with decoration """
        if not kwargs:
            kwargs = {}

        return authz_mod.wrap(
            journal.wrap(
                api_cls(**kwargs),
                self.journaler
            ),
            self.authorizer
        )
