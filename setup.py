#!/usr/bin/env python
"""Treadmill setup.py."""

import pip.req


def _read_requires(filename):
    reqs = []
    for inst_req in pip.req.parse_requirements(filename, session='no session'):
        req = str(inst_req.req)
        if not inst_req.match_markers():
            print('Skipping %r: %r => False' % (req, inst_req.markers))
            continue
        reqs.append(str(inst_req.req))
    return reqs


from setuptools import setup  # pylint: disable=wrong-import-position


setup(
    version='3.7',
    install_requires=_read_requires('requirements.txt'),
    setup_requires=_read_requires('test-requirements.txt')
)
