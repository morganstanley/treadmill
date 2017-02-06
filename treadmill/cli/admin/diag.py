"""Reports memory utilization details for given container."""


import os
import prettytable

import click

from treadmill import psmem
from treadmill import cgutils
from treadmill import utils


def init():
    """Top level command handler."""

    @click.group()
    def diag():
        """Local node and container diagnostics."""
        pass

    @diag.command(name='psmem')
    @click.option('--fast', is_flag=True, help='Disale statm/pss analysis.')
    @click.option('--cgroup', help='Cgroup to evaluate.')
    def psmem_cmd(fast, cgroup):
        """Reports memory utilization details for given container."""
        if cgroup:
            pids = cgutils.pids_in_cgroup('memory', cgroup)
        else:
            pids = [int(pid) for pid in os.listdir('/proc') if pid.isdigit()]

        use_pss = not fast
        memusage = psmem.get_memory_usage(pids, use_pss=use_pss)

        columns = (['name', 'count', 'private', 'shared', 'total'])
        table = prettytable.PrettyTable(columns)
        for column in columns:
            table.align[column] = 'l'

        table.set_style(prettytable.PLAIN_COLUMNS)
        table.left_padding_width = 0
        table.right_padding_width = 2

        readable = lambda value: utils.bytes_to_readable(value, power='B')
        for proc, info in sorted(memusage.items()):
            table.add_row([proc, info['count']] +
                          [readable(info[col]) for col in ['private',
                                                           'shared',
                                                           'total']])

        total = sum([info['total'] for info in memusage.values()])
        table.add_row(['', '', '', '', ''])
        table.add_row(['Total:', '', '', '', readable(total)])
        print(table)

        memusage, softmem, hardmem = cgutils.cgrp_meminfo(cgroup)
        print('')
        print('memory.usage     : ', readable(memusage))
        print('memory.softlimit : ', readable(softmem))
        print('memory.hardlimit : ', readable(hardmem))

    del psmem_cmd
    return diag
