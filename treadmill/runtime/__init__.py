"""Treadmill runtime framework."""

import os

from stevedore import driver


_RUNTIME_NAMESPACE = 'treadmill.runtime'


if os.name == 'posix':
    DEFAULT_RUNTIME = 'linux'
else:
    DEFAULT_RUNTIME = 'docker'


def get_runtime(runtime_name, tm_env, container_dir):
    """Gets the runtime implementation with the given name."""
    runtime_driver = driver.DriverManager(
        namespace=_RUNTIME_NAMESPACE,
        name=runtime_name,
        invoke_on_load=True,
        invoke_args=(tm_env, container_dir))

    if not runtime_driver:
        raise Exception('Runtime {0} is not supported.',
                        runtime_name)

    return runtime_driver.driver
