"""Helper tools for jsonschema."""


import os

import decorator
import jsonschema


_SCHEMA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'schemas'))

_TEST_MODE = False


def schema(*schemas, **kwschemas):
    """Schema decorator."""
    resolver = jsonschema.RefResolver('file://' + _SCHEMA_DIR + '/', None)
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

        if len(defaults):
            args = list(args)[:-len(defaults)]
        else:
            args = list(args)
        valid_args, valid_kwargs = validate(args, kwargs)
        if not _TEST_MODE:
            return func(*valid_args, **valid_kwargs)

    return decorated
