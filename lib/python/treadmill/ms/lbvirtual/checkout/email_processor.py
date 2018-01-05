"""LBVirtual checkout processor plugin (email).
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import email.mime
import time

import jinja2

from treadmill.ms.plugins.sproc import checkout


_EMAIL_INTERVAL = 60 * 60

_JINJA2_ENV = jinja2.Environment(loader=jinja2.PackageLoader(__name__))

_STATE = {
    'last_email': 0
}


def process(environment, cell, errors):
    """Process result of LBVirtual checkout.

    Checks if there are errors, sends notification email every hour.
    """

    if errors and time.time() - _STATE['last_email'] >= _EMAIL_INTERVAL:
        subject = 'LBVirtual checkout {}/{}: FAILURE'.format(cell, environment)

        template = _JINJA2_ENV.get_template('checkout-email')
        body = template.render(cell=cell, errors=errors)

        checkout.send_email(subject, email.mime.text.MIMEText(body, 'html'))
        _STATE['last_email'] = time.time()
