"""Render templates."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import re
import stat  # pylint: disable=wrong-import-order
import sys
import tempfile

import jinja2

if os.name == 'nt':
    # Pylint warning unable to import because it is on Windows only
    import win32api  # pylint: disable=E0401
    import win32con  # pylint: disable=E0401


_EXEC_MODE = (stat.S_IRUSR |
              stat.S_IRGRP |
              stat.S_IROTH |
              stat.S_IWUSR |
              stat.S_IXUSR |
              stat.S_IXGRP |
              stat.S_IXOTH)


def render(template, **kwargs):
    """Render template, adding new line in the end."""
    return re.sub(
        ' +',
        ' ',
        jinja2.Template(template).render(**kwargs)
    ).lstrip() + '\n'


def generate_template(templatename, **kwargs):
    """This renders a JINJA template as a generator.

    The templates exist in our lib/python/treadmill/templates directory.

    :param ``str`` templatename:
        The name of the template file.
    :param ``dict`` kwargs:
        key/value passed into the template.
    """
    jinja_env = jinja2.Environment(loader=jinja2.PackageLoader('treadmill'))
    template = jinja_env.get_template(templatename)
    return template.generate(**kwargs)


def create_script(filename, templatename, mode=_EXEC_MODE, **kwargs):
    """This Creates a file from a JINJA template.

    The templates exist in our lib/python/treadmill/templates directory.

    :param ``str`` filename:
        Name of the file to generate.
    :param ``str`` templatename:
        The name of the template file.
    :param ``int`` mode:
        The mode for the file (Defaults to +x).
    :param ``dict`` kwargs:
        key/value passed into the template.
    """
    jinja_env = jinja2.Environment(loader=jinja2.PackageLoader('treadmill'))

    filepath = os.path.dirname(filename)
    with tempfile.NamedTemporaryFile(dir=filepath,
                                     delete=False,
                                     mode='w') as f:
        data = jinja_env.get_template(templatename).render(**kwargs)
        f.write(data)
        if os.name == 'posix':
            # cast to int required in order for default _EXEC_MODE to work
            os.fchmod(f.fileno(), int(mode))

    if sys.version_info[0] < 3:
        # TODO: os.rename cannot replace on windows
        # (use os.replace in python 3.4)
        # copied from fs as utils cannot have this dependency
        if os.name == 'nt':
            win32api.MoveFileEx(f.name, filename,
                                win32con.MOVEFILE_REPLACE_EXISTING)
        else:
            os.rename(f.name, filename)
    else:
        os.replace(f.name, filename)
