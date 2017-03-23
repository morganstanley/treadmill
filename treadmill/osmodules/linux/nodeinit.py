"""Manages Treadmill node environment initialization."""


from ... import fs
from ... import iptables


def initialize(tm_env):
    """One time initialization of the Treadmill environment."""

    # Flush all rules in iptables nat and mangle tables (it is assumed that
    # none but Treadmill manages these tables) and bulk load all the
    # Treadmill static rules
    iptables.initialize(tm_env.host_ip)

    # Initialize network rules
    tm_env.rules.initialize()

    # Initialize FS plugins.
    fs.init_plugins(tm_env.root)
