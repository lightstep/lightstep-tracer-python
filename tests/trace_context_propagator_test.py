from unittest import TestCase

from lightstep import Tracer
from lightstep.propagation import TRACE_CONTEXT
from lightstep.trace_context import TraceContextPropagator


class TraceContextPropagatorTest(TestCase):
    def setUp(self):
        self._tracer = Tracer(
            periodic_flush_seconds=0,
            collector_host='localhost'
        )
        (
            self._tracer.
            register_propagator(TRACE_CONTEXT, TraceContextPropagator())
        )

    def tracer(self):
        return self._tracer

    def tearDown(self):
        self._tracer.flush()

    def test_extract(self):
        # FIXME Properly test that a randomly-initialized SpanContext is
        # returned here. Consider using a fixed random seed to make the tests
        # deterministic.
        self.tracer().extract(
            TRACE_CONTEXT, {
                "traceparent": "asdfas"
            }
        )

        self.tracer().extract(
            TRACE_CONTEXT, {
                "traceparent": "00-23-123-00"
            }
        )
