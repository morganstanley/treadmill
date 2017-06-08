"""
Cron execution modules.

The modules under this package do the actual cron execution.
"""
from treadmill import cron

CRON_EXEC_MODULE = '{}.run'.format(cron.CRON_MODULE)
