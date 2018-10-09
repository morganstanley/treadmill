"""Configures proper yaml representation.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import six

import yaml
from yaml import YAMLError
try:
    from yaml import CSafeLoader as Loader
    from yaml import CSafeDumper as Dumper
except ImportError:
    from yaml import SafeLoader as Loader
    from yaml import SafeDumper as Dumper


def _repr_bytes(dumper, data):
    """Fix byte string representation.
    """
    # We got bytes, convert to unicode
    unicode_data = data.decode()
    return _repr_unicode(dumper, unicode_data)


def _repr_unicode(dumper, data):
    """Fix unicode string representation.
    """
    if u'\n' in data:
        return dumper.represent_scalar(u'tag:yaml.org,2002:str', data,
                                       style='|')
    else:
        return dumper.represent_scalar(u'tag:yaml.org,2002:str', data)


if six.PY2:
    # pylint: disable=unicode-builtin,undefined-variable
    yaml.add_representer(str, _repr_bytes)
    yaml.add_representer(unicode, _repr_unicode)
else:
    yaml.add_representer(str, _repr_unicode)


def _repr_tuple(dumper, data):
    """Fix yaml tuple representation (use list).
    """
    return dumper.represent_list(list(data))


yaml.add_representer(tuple, _repr_tuple)


def _repr_none(dumper, _data):
    """Fix yaml None representation (use ~).
    """
    return dumper.represent_scalar(u'tag:yaml.org,2002:null', '~')


yaml.add_representer(type(None), _repr_none)


def dump(*args, **kwargs):
    """Delegate to yaml dumps.
    """
    if kwargs is None:
        kwargs = {}
    kwargs['Dumper'] = Dumper
    return yaml.dump(*args, **kwargs)


def load(*args, **kwargs):
    """Delegate to yaml load.
    """
    if kwargs is None:
        kwargs = {}
    kwargs['Loader'] = Loader
    return yaml.load(*args, **kwargs)


def load_all(*args, **kwargs):
    """Delegate to yaml loadall.
    """
    if kwargs is None:
        kwargs = {}
    kwargs['Loader'] = Loader
    return yaml.load_all(*args, **kwargs)


__all__ = [
    'dump',
    'load',
    'load_all',
    'YAMLError'
]
