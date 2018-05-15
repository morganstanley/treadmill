"""Helper tools for jsonschema.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json

import decorator
import jsonschema
import pkg_resources


_TEST_MODE = False


class _RefResolver(jsonschema.RefResolver):
    """Resolves schema from pkg resource."""

    def __init__(self):
        super(_RefResolver, self).__init__(
            'file://treadmill/etc/schema/',
            None
        )

    def resolve_remote(self, uri):
        """Resolves json schema from package resource."""
        # TODO: specyfying file:// uri is wrong, but for some reason
        #       documented ways of handling differnet uri type (using handlers
        #       dict) do not work with local ref points like #/<xxx>.
        if uri.startswith('file://'):
            resource = uri[len('file://'):]
            pkg, path = resource.split('/', 1)
            json_string = pkg_resources.resource_string(
                pkg, path
            )
            return json.loads(json_string.decode('utf8'))
        else:
            return super(_RefResolver, self).resolve_remote(uri)


def schema(*schemas, **kwschemas):
    """Schema decorator."""
    resolver = _RefResolver()
    validators = [
        jsonschema.Draft4Validator(s, resolver=resolver)
        for s in schemas
    ]

    kwvalidator = jsonschema.Draft4Validator({
        'type': 'object',
        'additionalProperties': False,
        'properties': kwschemas,
    }, resolver=resolver)

    def validate(args, kwargs):
        """Validate function arguments."""
        validated_args = []
        for validator, arg in zip(validators, args):
            validator.validate(arg)
            validated_args.append(arg)
        if kwargs:
            kwvalidator.validate(kwargs)

        return validated_args, kwargs

    @decorator.decorator
    def decorated(func, *args):
        """Validates arguments given schemas."""
        # decorator.decorator swallows kwargs for some reason.
        argspec = decorator.getargspec(func)
        defaults = []
        if argspec.defaults:
            defaults = argspec.defaults

        kwargs = {}
        for kw_name, kw_value, kw_default in zip(reversed(argspec.args),
                                                 reversed(args),
                                                 defaults):
            if kw_value != kw_default:
                kwargs[kw_name] = kw_value

        if defaults:
            args = list(args)[:-len(defaults)]
        else:
            args = list(args)
        valid_args, valid_kwargs = validate(args, kwargs)
        if not _TEST_MODE:
            return func(*valid_args, **valid_kwargs)
        else:
            return None

    return decorated
