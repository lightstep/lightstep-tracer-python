import unittest

import lightstep
from lightstep.propagation import LightStepFormat


class EnvoyPropagatorTest(unittest.TestCase):
    def setUp(self):
        self._tracer = lightstep.Tracer(
                periodic_flush_seconds=0,
                collector_host='localhost')

    def tracer(self):
        return self._tracer

    def tearDown(self):
        self._tracer.flush()

    def testInjectExtract(self):
        carrier = bytearray()
        span = self.tracer().start_span('Sending request')
        span.set_baggage_item('checked', 'baggage')

        self.tracer().inject(span.context, LightStepFormat.ENVOY_HEADERS, carrier)

        result = self.tracer().extract(LightStepFormat.ENVOY_HEADERS, carrier)
        self.assertEqual(span.context.span_id, result.span_id)
        self.assertEqual(span.context.trace_id, result.trace_id)
        self.assertEqual(span.context.baggage, result.baggage)
        self.assertEqual(span.context.sampled, result.sampled)


if __name__ == '__main__':
    unittest.main()