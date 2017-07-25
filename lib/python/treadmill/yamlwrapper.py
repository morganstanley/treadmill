"""Configures proper yaml representation."""

import yaml
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


def _repr_unicode(dumper, data):
    """Fix yaml str representation."""
    ascii_data = data.encode('ascii', 'ignore')
    if '\n' in data:
        return dumper.represent_scalar(u'tag:yaml.org,2002:str', ascii_data,
                                       style='|')
    else:
        return dumper.represent_scalar(u'tag:yaml.org,2002:str', ascii_data)


def _repr_tuple(dumper, data):
    """Fix yaml tuple representation (use list)."""
    return dumper.represent_list(list(data))


def _repr_none(dumper, data_unused):
    """Fix yaml None representation (use ~)."""
    return dumper.represent_scalar(u'tag:yaml.org,2002:null', '~')


# This will be invoked on module import once.
yaml.add_representer(unicode, _repr_unicode)
yaml.add_representer(str, _repr_unicode)
yaml.add_representer(tuple, _repr_tuple)
yaml.add_representer(type(None), _repr_none)


def dump(*args, **kwargs):
    """Delegate to yaml dumps."""
    return yaml.dump(*args, **kwargs)


def load(*args, **kwargs):
    """Delegate to yaml load."""
    if kwargs is None:
        kwargs = {}
    kwargs['Loader'] = Loader
    return yaml.load(*args, **kwargs)


def load_all(*args, **kwargs):
    """Delegate to yaml loadall."""
    if kwargs is None:
        kwargs = {}
    kwargs['Loader'] = Loader
    return yaml.load_all(*args, **kwargs)


YAMLError = yaml.YAMLError
