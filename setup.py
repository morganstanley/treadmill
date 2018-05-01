#!/usr/bin/env python
"""Treadmill setup.py.
"""

import setuptools

# pip 10.0 moved req to _internal. Need to find better solution, changing
# for now so that build pass.
try:
    import pip.req as pip_req
except ImportError:
    import pip._internal.req as pip_req


def _read_requires(filename):
    reqs = []
    for inst_req in pip_req.parse_requirements(filename, session='no session'):
        req = str(inst_req.req)
        if inst_req.markers:
            req += '; %s' % inst_req.markers
        reqs.append(req)
    return reqs


setuptools.setup(
    version='3.7',
    install_requires=_read_requires('requirements.txt'),
)
