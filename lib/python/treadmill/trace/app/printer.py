"""App trace printer.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from treadmill import utils

from treadmill.appcfg import abort as app_abort

from . import events


class AppTracePrinter(events.AppTraceEventHandler):
    """Output out trace events.
    """

    def on_scheduled(self, when, instanceid, server, why):
        """Invoked when task is scheduled.
        """
        if why:
            print('%s - %s scheduled on %s: %s' % (
                utils.strftime_utc(when), instanceid, server, why
            ))
        else:
            print('%s - %s scheduled on %s' % (
                utils.strftime_utc(when), instanceid, server))

    def on_pending(self, when, instanceid, why):
        """Invoked when task is pending.
        """
        if why:
            print('%s - %s pending: %s' % (
                utils.strftime_utc(when), instanceid, why))
        else:
            print('%s - %s pending' % (
                utils.strftime_utc(when), instanceid))

    def on_pending_delete(self, when, instanceid, why):
        """Invoked when task is about to be deleted.
        """
        if why:
            print('%s - %s pending delete: %s' % (
                utils.strftime_utc(when), instanceid, why))
        else:
            print('%s - %s pending delete' % (
                utils.strftime_utc(when), instanceid))

    def on_configured(self, when, instanceid, server, uniqueid):
        """Invoked when task is configured
        """
        print('%s - %s/%s configured on %s' % (
            utils.strftime_utc(when), instanceid, uniqueid, server
        ))

    def on_deleted(self, when, instanceid):
        """Invoked when task is deleted.
        """
        print('%s - %s deleted' % (utils.strftime_utc(when), instanceid))

    def on_finished(self, when, instanceid, server, signal, exitcode):
        """Invoked when task is finished.
        """
        print('%s - %s finished on %s' % (
            utils.strftime_utc(when), instanceid, server))

    def on_killed(self, when, instanceid, server, is_oom):
        """Default task-finished handler.
        """
        if is_oom:
            print('%s - %s killed, out of memory' % (
                utils.strftime_utc(when), instanceid))
        else:
            print('%s - %s killed' % (
                utils.strftime_utc(when), instanceid))

    def on_aborted(self, when, instanceid, server, why):
        """Invoked when task is aborted.
        """
        try:
            why = app_abort.AbortedReason(why)
        except ValueError:
            why = app_abort.AbortedReason.UNKNOWN

        print('%s - %s aborted on %s [reason: %s]' % (
            utils.strftime_utc(when), instanceid, server, why.description()))

    def on_service_running(self, when, instanceid, server, uniqueid, service):
        """Invoked when service is running.
        """
        print('%s - %s/%s/service/%s running' % (
            utils.strftime_utc(when),
            instanceid,
            uniqueid,
            service,
        ))

    def on_service_exited(self, when, instanceid, server,
                          uniqueid, service, exitcode, signal):
        """Invoked when service exits.
        """
        if exitcode > 255:
            print('%s - %s/%s/service/%s killed, signal: %s' % (
                utils.strftime_utc(when),
                instanceid,
                uniqueid,
                service,
                utils.signal2name(signal)
            ))
        else:
            print('%s - %s/%s/service/%s exited, return code: %s' % (
                utils.strftime_utc(when),
                instanceid,
                uniqueid,
                service,
                exitcode
            ))
