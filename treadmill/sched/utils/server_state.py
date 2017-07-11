import enum


# Disable pylint complaint about not having __init__
#
# pylint: disable=W0232
class State(enum.Enum):
    """Enumeration of node/server states."""

    # Ready to accept new applications.
    # pylint complains: Invalid class attribute name "up"
    up = 'up'  # pylint: disable=C0103

    # Applications need to be migrated.
    down = 'down'

    # Existing applications can stay, but will not accept new.
    frozen = 'frozen'
