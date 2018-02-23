import unittest

from opentracing.harness.api_check import APICompatibilityCheckMixin

import lightstep.tracer


class LightStepTracerOpenTracingCompatibility(unittest.TestCase, APICompatibilityCheckMixin):
    """This unittest currently passes, but then the "Flush Thread" drops a stack trace.

    I believe this is a concurrency problem because this is the first time we have multiple instances of Runtime running in a single binary.
    """
    def setUp(self):
        self._tracer = lightstep.Tracer(
                periodic_flush_seconds=0,
                collector_host='localhost')

    def tracer(self):
        return self._tracer

    def is_parent(self, parent, span):
        if span is None:
            return False

        if parent is None:
            return span.parent_id is None

        return parent.context.span_id == span.parent_id

    def tearDown(self):
        self._tracer.flush()


if __name__ == '__main__':
    unittest.main()
