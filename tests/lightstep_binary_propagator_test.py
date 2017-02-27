import unittest

import lightstep
from lightstep.propagation import LightStepFormat


class LightStepBinaryPropagatorTest(unittest.TestCase):
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

        self.tracer().inject(span.context, LightStepFormat.LIGHTSTEP_BINARY, carrier)

        result = self.tracer().extract(LightStepFormat.LIGHTSTEP_BINARY, carrier)
        self.assertEqual(span.context.span_id, result.span_id)
        self.assertEqual(span.context.trace_id, result.trace_id)
        self.assertEqual(span.context.baggage, result.baggage)
        self.assertEqual(span.context.sampled, result.sampled)

    def testExtractionOfKnownInput(self):
        # Test extraction of a well - known input, for validation with other libraries.
        input = "EigJOjioEaYHBgcRNmifUO7/xlgYASISCgdjaGVja2VkEgdiYWdnYWdl"
        result = self.tracer().extract(LightStepFormat.LIGHTSTEP_BINARY, bytearray(input))
        self.assertEqual(6397081719746291766L, result.span_id)
        self.assertEqual(506100417967962170L, result.trace_id)
        self.assertEqual(True, result.sampled)
        self.assertDictEqual(result.baggage, {"checked" : "baggage"})


if __name__ == '__main__':
    unittest.main()