"""Treadmill alert module."""

import io
import json
import os.path
import time

from treadmill import fs


def create(
        alerts_dir,
        epoch_ts=None,
        instanceid=None,
        summary=None,
        type_=None,
        **kwargs
):
    """Create a file in alerts_dir representing the alert."""
    fs.write_safe(
        os.path.join(alerts_dir, _to_filename(instanceid, type_)),
        lambda f: f.write(
            json.dumps(
                dict(
                    epoch_ts=epoch_ts or time.time(),
                    instanceid=instanceid,
                    summary=summary,
                    type_=type_,
                    **kwargs),
                indent=4
            ).encode()
        ),
        permission=0o644)


def _to_filename(instanceid, type_):
    """Returns a host wide unique filename for the alert.

    Alerts sorted alphabetically result in chronological order.
    """
    return '{:f}-{}-{}'.format(time.monotonic(), instanceid, type_)


def read(filename, alerts_dir=None):
    """Return the alert stored in the file and delete the file."""
    if alerts_dir is not None:
        filename = os.path.join(alerts_dir, filename)

    with io.open(filename, 'rb') as file_:
        alert = json.loads(file_.read().decode())

    return alert
