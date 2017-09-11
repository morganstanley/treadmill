from treadmill import authz
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

        def delete(hostname):
            result = subprocess.check_output([
                "ipa",
                "host-del",
                hostname,
            ]).decode('utf-8')

            assert 'Deleted host "' + hostname + '"' in result

        def ipa_service_add(args):
            domain = args.get('domain')
            hostname = args.get('hostname')
            _service = args.get('service')
            _service_with_domain = _service + '@' + domain.upper()

            subprocess.check_output([
                "ipa",
                "service-add",
                "--force",
                _service
            ])

            result = subprocess.check_output([
                "ipa",
                "service-allow-retrieve-keytab",
                _service_with_domain,
                "--hosts=" + hostname
            ])

            result = result.decode('utf-8').strip().split("\n")[-2]
            assert 'members added 1' in result

        self.create = create
        self.delete = delete
        self.ipa_service_add = ipa_service_add


def init(authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return authz.wrap(api, authorizer)
