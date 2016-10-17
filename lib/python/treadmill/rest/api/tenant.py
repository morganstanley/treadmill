"""
Treadmill Tenant REST api.
"""
from __future__ import absolute_import

# For some reason pylint complains about restplus not being able to import.
#
# pylint: disable=E0611,F0401
import flask.ext.restplus as restplus
import flask

from treadmill import webutils


# Old style classes, no init method.
#
# pylint: disable=W0232
def init(api, cors, impl):
    """Configures REST handlers for tenant resource."""

    namespace = webutils.namespace(
        api, __name__, 'Tenant REST operations'
    )

    @namespace.route('/',)
    class _TenantList(restplus.Resource):
        """Treadmill Tenant resource"""

        @webutils.get_api(api, cors)
        def get(self):
            """Returns list of configured tenants."""
            return impl.list()

    @namespace.route('/<tenant_id>')
    class _TenantResource(restplus.Resource):
        """Treadmill Tenant resource."""

        @webutils.get_api(api, cors)
        def get(self, tenant_id):
            """Return Treadmill tenant configuration."""
            return impl.get(tenant_id)

        @webutils.delete_api(api, cors)
        def delete(self, tenant_id):
            """Deletes Treadmill tenant."""
            return impl.delete(tenant_id)

        @webutils.put_api(api, cors)
        def put(self, tenant_id):
            """Updates Treadmill tenant configuration."""
            return impl.update(tenant_id, flask.request.json)

        @webutils.post_api(api, cors)
        def post(self, tenant_id):
            """Creates Treadmill tenant."""
            return impl.create(tenant_id, flask.request.json)
