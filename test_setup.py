def _setup_pypath():
    import inspect
    import os.path
    import sys

    curfile=inspect.getframeinfo(inspect.currentframe()).filename
    basedir = os.path.realpath(os.path.dirname(curfile) or '.')
    sys.path.extend(
                    [
                        os.path.join(basedir, 'lib', 'python'),
                        os.path.join(basedir, 'tests'),
                    ]
                   )

_setup_pypath()
del _setup_pypath

