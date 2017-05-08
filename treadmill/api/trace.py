"""Implementation of state API."""


import logging

from .. import context
from .. import schema
from .. import exc
from .. import zknamespace as z


_LOGGER = logging.getLogger(__name__)


class API(object):
    """Treadmill State REST api."""

    def __init__(self):

        zkclient = context.GLOBAL.zk.conn

        cell_state = {
            'tasks': {}
        }

        def _watch_app_tasks(app_task_path, app_task_info):
            """Define a watcher that will update app_task_info for each of the
            app names.
            """

            @exc.exit_on_unhandled
            @zkclient.ChildrenWatch(app_task_path)
            def _watch_task(instanceids):
                app_task_info[:] = instanceids
                return True

        @exc.exit_on_unhandled
        @zkclient.ChildrenWatch(z.TASKS)
        def _watch_tasks(tasks):
            """Watch /tasks data."""

            tasks_set = set(tasks)
            for new_task in tasks_set - cell_state['tasks'].keys():
                app_task_path = z.path.task(new_task)
                app_task_info = cell_state['tasks'].setdefault(new_task, [])

                _watch_app_tasks(app_task_path, app_task_info)

            for task in cell_state['tasks']:
                if task not in tasks_set:
                    cell_state['tasks'].pop(task)

            return True

        @schema.schema({'$ref': 'app.json#/resource_id'})
        def get(rsrc_id):
            """Get trace information for a given application name.
            """
            tasks = cell_state['tasks'].get(rsrc_id)
            if tasks:
                return {
                    'name': rsrc_id,
                    'instances': tasks
                }
            return None

        self.get = get


def init(_authorizer):
    """Returns module API wrapped with authorizer function."""
    # There is no authorization for state api.
    return API()
