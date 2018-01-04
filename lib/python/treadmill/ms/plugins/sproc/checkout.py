"""Cell checkout plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import smtplib
from email.mime import text
from email.mime import multipart

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import alert


_LOGGER = logging.getLogger(__name__)


class State(object):
    """Holds last state."""
    was_successful = None
    errors = None
    failures = None

    @classmethod
    def changed(cls, was_successful, errors, failures):
        """Check if state changed."""
        if errors is not None and failures is not None:
            different = bool(
                (cls.was_successful != was_successful) or
                (cls.errors ^ set(errors)) and
                (cls.failures ^ set(failures))
            )
        else:
            different = cls.was_successful != was_successful

        cls.was_successful = was_successful
        if errors is not None:
            cls.errors = set(errors)
        else:
            cls.errors = set()
        if failures is not None:
            cls.failures = set(failures)
        else:
            cls.failures = set()

        return different


def send_email(subject, body):
    """Sends notification email."""
    to_list = ['treadmill-support@ms.com']
    _LOGGER.info('Send email: %r', to_list)

    sender = smtplib.SMTP()
    sender.connect('msa-hub.ms.com')

    outer = multipart.MIMEMultipart()
    outer['Subject'] = subject
    outer['To'] = ', '.join(to_list)
    outer['Cc'] = []
    outer['From'] = 'treadmill-monitor'
    outer['Reply-To'] = 'treadmill-support@ms.com'

    outer.attach(body)

    sender.sendmail(outer['From'], to_list, outer.as_string())
    sender.close()
    _LOGGER.info('Alert email sent.')


def process(cell, report_url, result):
    """Process result of cell checkout.

    Checks if state is different from last, sends notification email.
    """

    if result is not None:
        was_successful = result.wasSuccessful()
        failures = [test_case.id() for test_case, _trace in result.failures]
        errors = [test_case.id() for test_case, _trace in result.errors]

    else:
        was_successful = None
        failures = None
        errors = None

    if State.changed(was_successful, errors, failures):
        if was_successful:
            subject = 'Cell checkout SUCCESS: %s' % cell
            body = 'Success: %s' % report_url
        else:
            subject = 'Cell checkout FAILURE: %s' % cell
            body = 'Failure: %s' % report_url

        try:
            alert.send_event(
                event_type='cell.checkout',
                instanceid=cell,
                summary=body,
                success='1' if was_successful else '0'
            )
        except Exception:  # pylint: disable=W0703
            _LOGGER.exception('Failed to send watchtower event.')

        try:
            send_email(subject, text.MIMEText(body))
        except Exception:  # pylint: disable=W0703
            _LOGGER.exception('Failed to send alert email.')
