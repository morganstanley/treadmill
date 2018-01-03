class LDAPNotFound(Exception):
    """When LDAP server is not provisioned."""

    def __init__(self):
        self.message = 'LDAPNotFound: Please check if LDAP Server is up and running.' # noqa

    def __str__(self):
        return self.message


class IPAServerNotFound(Exception):
    """When IPA server is not provisioned"""

    def __init__(self):
        self.message = 'IPAServerNotFound: Please check if IPA Server is up and running.' # noqa

    def __str__(self):
        return self.message
