import unittest
import lightstep
from lightstep.propagation import LightStepFormat
import sys

class LightStepBinaryPropagatorTest(unittest.TestCase):
    def setUp(self):
        self._tracer = lightstep.Tracer(
            access_token="3c2e7386088c2a26b295e48ac1221290",
            periodic_flush_seconds=1,
            verbosity=5,
            collector_host="collector-staging.lightstep.com",
            collector_port=80,
            collector_encryption="none")

    def tracer(self):
        return self._tracer

    # def tearDown(self):
        # self._tracer.flush()

    def testInjectExtract(self):
        carrier = bytearray()
        span = self.tracer().start_span('Sending request')
        span.set_baggage_item('checked', 'baggage')

        self.tracer().inject(span.context, LightStepFormat.LIGHTSTEP_BINARY, carrier)
        self.tracer().record(span)

        result = self.tracer().extract(LightStepFormat.LIGHTSTEP_BINARY, carrier)
        self.assertEqual(span.context.span_id, result.span_id)
        self.assertEqual(span.context.trace_id, result.trace_id)
        self.assertEqual(span.context.baggage, result.baggage)
        self.assertEqual(span.context.sampled, result.sampled)
        self.assertEqual("Hello", "world")

    # def testExtractionOfKnownInput(self):
    #     print >> sys.stderr, "EXTRACTION OF KNOWN INPUT TEST"
    #     # Test extraction of a well - known input, for validation with other libraries.
    #     input = "EigJOjioEaYHBgcRNmifUO7/xlgYASISCgdjaGVja2VkEgdiYWdnYWdl"
    #     result = self.tracer().extract(LightStepFormat.LIGHTSTEP_BINARY, bytearray(input))
    #     self.assertEqual(6397081719746291766L, result.span_id)
    #     self.assertEqual(506100417967962170L, result.trace_id)
    #     self.assertEqual(True, result.sampled)
    #     self.assertDictEqual(result.baggage, {"checked" : "baggage"})
    #     self.assertEqual("hello", "world")


if __name__ == '__main__':
    unittest.main()