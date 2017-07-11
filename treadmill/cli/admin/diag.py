"""Reports memory utilization details for given container.
"""

import os

import click
import prettytable

from treadmill import psmem
from treadmill import cgutils
from treadmill import metrics
from treadmill import utils


def init():
    """Top level command handler."""

    @click.group()
    def diag():
        """Local node and container diagnostics."""
        pass

    @diag.command(name='psmem')
    @click.option('--fast', is_flag=True, help='Disable statm/pss analysis.')
    @click.option('-v', '--verbose', is_flag=True, help='Verbose')
    @click.option('--percent', is_flag=True)
    @click.argument('app')
    def psmem_cmd(fast, app, verbose, percent):
        """Reports memory utilization details for given container."""
        if app.find('#') == -1:
            raise click.BadParameter('Specify full instance name: xxx#nnn')
        app = app.replace('#', '-')

        cgroup = None
        apps = os.listdir('/sys/fs/cgroup/memory/treadmill/apps')
        for entry in apps:
            if app in entry:
                cgroup = os.path.join('/treadmill/apps', entry)
        if not cgroup:
            raise click.BadParameter('Could not find corresponding cgroup')

        pids = cgutils.pids_in_cgroup('memory', cgroup)

        use_pss = not fast
        memusage = psmem.get_memory_usage(pids, verbose, use_pss=use_pss)

        proc_columns = (['ppid', 'name', 'threads', 'private', 'shared',
                         'total'])
        proc_table = prettytable.PrettyTable(proc_columns)
        proc_table.align = 'l'

        proc_table.set_style(prettytable.PLAIN_COLUMNS)
        proc_table.left_padding_width = 0
        proc_table.right_padding_width = 2

        total = sum([info['total'] for info in memusage.values()])

        readable = lambda value: utils.bytes_to_readable(value, power='B')
        percentage = lambda value, total: "{:.1%}".format(value / total)
        cols = proc_columns[3:]
        for proc, info in sorted(memusage.items()):
            row_base = [proc, info['name'], info['threads']]
            row_values = None
            if percent:
                row_values = [percentage(info[col], total) for col in cols]
            else:
                row_values = [readable(info[col]) for col in cols]
            proc_table.add_row(row_base + row_values)

        proc_table.add_row(['', '', '', '', '', ''])
        proc_table.add_row(['Total:', '', '', '', '', readable(total)])
        print(proc_table)

        metric = metrics.read_memory_stats(cgroup)

        total_table = prettytable.PrettyTable(['memory', 'value'])
        total_table.align['memory'] = 'l'
        total_table.align['value'] = 'r'

        total_table.set_style(prettytable.PLAIN_COLUMNS)
        total_table.header = False

        # Actual memory usage is without the disk cache
        memory_usage = readable(metric['memory.usage_in_bytes'] -
                                metric['memory.stats']['cache'])

        total_table.add_row(['usage', memory_usage])
        total_table.add_row(['', percentage(metric['memory.usage_in_bytes'],
                                            metric['memory.limit_in_bytes'])])
        total_table.add_row(['diskcache',
                             readable(metric['memory.stats']['cache'])])

        total_table.add_row(['softlimit',
                             readable(metric['memory.soft_limit_in_bytes'])])
        total_table.add_row(['hardlimit',
                             readable(metric['memory.limit_in_bytes'])])

        print('')
        print(total_table)

    del psmem_cmd
    return diag
