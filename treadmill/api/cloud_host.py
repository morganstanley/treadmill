from .. import authz
import subprocess


class API(object):
    """Treadmill Cloud Host REST API."""

    def __init__(self):

        def create(hostname):
            result = subprocess.check_output([
                "ipa",
                "host-add",
                hostname,
                "--random",
                "--force"
            ])
            password_string = result.decode('utf-8').split("\n")[4]
            return password_string.split("password:")[-1].strip()

        self.create = create


def init(authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return authz.wrap(api, authorizer)
