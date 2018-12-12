"""Get node data
node data from configs/node.json
It is a combination of cell data and node data
"""

import io
import json
import logging
import os

_LOGGER = logging.getLogger(__name__)

FILE = 'node.json'


def get(config_dir):
    """Get node data
    """
    node_file = os.path.join(config_dir, FILE)
    try:
        with io.open(node_file) as f:
            data = json.load(f)
    except FileNotFoundError:
        _LOGGER.warning('node config file %s not found', node_file)
        data = {}

    return data
