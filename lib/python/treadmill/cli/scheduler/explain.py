"""Explain why an application instance is in pending state.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click
import pandas as pd

from six.moves import urllib

from treadmill import (cli, context)
from treadmill.cli.scheduler import print_report
from treadmill import restclient

# let's handle HTTP 409 (AlreadyExistsError in the explain() func. locally
_EXCEPTIONS = [
    ex for ex in restclient.CLI_REST_EXCEPTIONS
    if ex[0] != restclient.AlreadyExistsError
]


def init():
    """Return top level command handler."""

    @click.command()
    @cli.handle_exceptions(_EXCEPTIONS)
    @click.argument('instance')
    def explain(instance):
        """Explain why an instance is pending."""
        api_urls = context.GLOBAL.cell_api()
        path = '/scheduler/explain/{}'.format(urllib.parse.quote(instance))

        try:
            response = restclient.get(api_urls, path).json()
        except restclient.AlreadyExistsError:
            cli.out('Instance {} is running.'.format(instance))
        else:
            report = pd.DataFrame(
                response['data'], columns=response['columns']
            )
            print_report(report, explain=True)

    return explain
