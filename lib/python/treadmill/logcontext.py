"""Treadmill log context helper classes."""


import logging


class Adapter(logging.LoggerAdapter):
    """
    Prepends the log messages with the str representation of the internal
    'extra' atribute if there's any.

    This adapter makes possible to
    * insert additional information into the log records w/o having to alter
      the "main log record format" defined in the etc/logging/*.yml files
    * use logging (_LOGGER) in the same way as before apart from the
      initialization of _LOGGER in a given modul
    """

    def __init__(self, logger, extra=None):
        """
        Allows to initialize w/o providing any 'extra' value.
        """
        super(Adapter, self).__init__(logger, extra)

    def process(self, msg, kwargs):
        """
        Add extra content to the log line and don't modify it if no extra
        content is defined.
        """
        if not self.extra:
            return msg, kwargs

        return '%s - %s' % (self._fmt(self.extra), msg), kwargs

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

    def __init__(self, logger_adapter, extra=None):
        self.logger_adapter = logger_adapter
        self.extra = extra
        self.old_extra = None

    def __enter__(self):
        """
        Save the original internal state of the logger adapter and
        replace it with the one got when instantiated.
        """
        self.old_extra = self.logger_adapter.extra
        self.logger_adapter.extra = self.extra

    def __exit__(self, *args):
        """Restore the original internal state of the logger adapter."""
        self.logger_adapter.extra = self.old_extra
