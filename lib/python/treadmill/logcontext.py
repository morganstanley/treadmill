"""Treadmill log context helper classes."""

import logging
import threading

LOCAL_ = threading.local()
LOCAL_.ctx = []


class Adapter(logging.LoggerAdapter):
    """
    Prepends the log messages with the str representation of the thread local
    list's last element if there's any.

    This adapter makes possible to
    * insert additional information into the log records w/o having to alter
      the log formatter's definition inited by the etc/logging/*.yml files
    * use logging (_LOGGER) in the same way as before apart from the
      initialization of _LOGGER in a given modul
    """

    def __init__(self, logger, extra=None):
        """
        Allow initializing w/o any 'extra' value.
        """
        super(Adapter, self).__init__(logger, extra)

        if self.extra:
            self.extra = [self.extra]
        else:
            self.extra = LOCAL_.ctx

    def warn(self, msg, *args, **kwargs):
        """
        Delegate warn() to warning().

        This is provided as a convenience method in Logger but it is apparently
        missing from LoggerAdapter, see

        https://hg.python.org/cpython/file/2.7/Lib/logging/__init__.py#l1181
        """
        self.warning(msg, *args, **kwargs)

    def process(self, msg, kwargs):
        """
        Add extra content to the log line but don't modify it if no element
        is contained by the thread local variable.
        """
        if not self.extra:
            return msg, kwargs

        return '%s - %s' % (self._fmt(self.extra[-1]), msg), kwargs

    def _fmt(self, extra):
        """Format the 'extra' content as it will be represented in the logs."""
        return extra


class ContainerAdapter(Adapter):
    """
    Adapter to insert application unique name into the log record.
    """

    def _fmt(self, extra):
        """Format the 'extra' content as it will be represented in the logs."""
        (app_name, inst_id, uniq_id) = self._dec_unique_name(extra)
        return "{name}#{inst} {uniq}".format(name=app_name,
                                             inst=inst_id,
                                             uniq=uniq_id)

    def _dec_unique_name(self, unique_name):
        """
        Decompose unique app name into a list containing the app name,
        instance id and unique id. Return dummy entries if not an app unique
        name is passed in params.
        """
        parts = unique_name.rsplit('-', 2)

        if len(parts) != 3:
            return ['_'] * 3

        return parts


class LogContext(object):
    """
    Context manager wrapping a logger adapter instance.

    Ensures that a log record is processed always by the log adapter and the
    corresponding internal sttate without having to worry about restoring the
    logger's state to its original in case of an exception etc.
    """

    def __init__(self, logger, extra, adapter_cls=Adapter):
        self.extra = extra
        self.logger = logger
        self.adapter_cls = adapter_cls

    def __enter__(self):
        """
        Save the original internal state of the logger adapter and
        replace it with the one got when instantiated.
        """
        LOCAL_.ctx.append(self.extra)
        return self.adapter_cls(self.logger)

    def __exit__(self, *args):
        """Restore the original internal state of the logger adapter."""
        LOCAL_.ctx.pop()
