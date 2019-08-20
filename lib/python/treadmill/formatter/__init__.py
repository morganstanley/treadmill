"""Formatters."""


def _empty(value):
    if value is None:
        return True

    if isinstance(value, dict) and not value:
        return True

    if isinstance(value, list) and not value:
        return True

    return False


def sanitize(obj):
    """Remove fields that are None."""
    if isinstance(obj, dict):
        for key, value in list(obj.items()):
            if key == 'environ':
                continue
            new_v = sanitize(value)
            if _empty(new_v):
                del obj[key]
            else:
                obj[key] = sanitize(value)
        return obj
    elif isinstance(obj, list):
        return [sanitize(elem) for elem in obj]
    else:
        return obj
