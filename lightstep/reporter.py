import logging
import pprint

from . import instrument, util

DEFAULT_LOGGER = logging.getLogger(__name__)


class NullReporter(object):
    """Ignores all spans."""
    def __init__(self):
        self._runtime_guid = util._generate_guid()
        self.logger = logger if logger else DEFAULT_LOGGER

    def report_span(self, span):
        pass

    def flush(self):
        return True

def _pretty_logs(logs):
    return ''.join(['\n  ' + pprint.pformat(log) for log in logs])

class LoggingReporter(object):
    """Logs all spans to console."""
    def __init__(self, logger=None):
        self._runtime_guid = util._generate_guid()
        self.logger = logger if logger else DEFAULT_LOGGER

    def report_span(self, span):
        logging.warn('Reporting span %s \n with logs %s', pprint.pformat(vars(span.span_record)), _pretty_logs(span.logs))

    def flush(self):
        return True

class LightStepReporter(object):
    def __init__(self, *args, **kwargs):
        self.runtime = instrument.Runtime(*args, **kwargs)
        self._runtime_guid = self.runtime._runtime.guid

    def report_span(self, span):
        self.runtime._add_span(span.span_record)
        for log in span.logs:
            self.runtime._add_log(log)

    def flush(self):
        self.runtime.flush()
        return True

class MockReporter(object):
    """MockReporter is used to debug and test Tracer."""
    def __init__(self):
        self._runtime_guid = util._generate_guid()
        self.spans = []

    def report_span(self, span):
        self.spans.append(span)

    def flush():
        pass

    def clear(self):
        """Delete the current spans."""
        self.spans[:] = []
