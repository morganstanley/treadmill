"""API package."""


import pkgutil


__path__ = pkgutil.extend_path(__path__, __name__)


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
    norm = {key: value for key, value in rsrc.items() if not _empty(value)}
    for key, value in norm.items():
        norm[key] = normalize(value)
    return norm


def normalize_list(rsrc):
    """Normalize list."""
    return [normalize(item)
            for item in rsrc if not _empty(item)]
