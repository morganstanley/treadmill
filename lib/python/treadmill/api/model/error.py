"""
Error API data models
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from flask_restplus import fields


ERROR_ID_WHY_FIELDS = {
    '_id': fields.String(description='Application ID'),
    'why': fields.String(description='Why the error?'),
}


def models(api):
    """Get the error models"""
    erorr_id_why = api.model('ErrorIdWhy', ERROR_ID_WHY_FIELDS)
    error_model = api.model('ErrorResp', {
        '_error': fields.Nested(erorr_id_why),
    })

    return erorr_id_why, error_model
