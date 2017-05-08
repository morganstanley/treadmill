"""Treadmill websocket utilities."""

import collections


def parse_message_filter(message_filter):
    """Helper function to prepare and parse message filter."""
    if '#' not in message_filter:
        message_filter += '#*'
    appname, instanceid = message_filter.split('#', 1)
    return collections.namedtuple('ParseResult', 'filter appname instanceid')(
        message_filter, appname, instanceid
    )
