from unittest import TestCase

from pytest import raises
from opentracing import SpanContextCorruptedException

from opentracing import Format
from lightstep import Tracer
from lightstep.b3_propagator import B3Propagator


class B3PropagatorTest(TestCase):
    def setUp(self):
        self._tracer = Tracer(
            periodic_flush_seconds=0,
            collector_host="localhost"
        )
        self._tracer.register_propagator(Format.HTTP_HEADERS, B3Propagator())

    def tracer(self):
        return self._tracer

    def tearDown(self):
        self._tracer.flush()

    def test_inject(self):
        carrier = {}
        span = self.tracer().start_span("test_inject")
        span.set_baggage_item("checked", "baggage")
        self.tracer().inject(span.context, Format.HTTP_HEADERS, carrier)
        self.assertEqual(
            carrier,
            {
                "x-b3-traceid": (
                    format(span.context.trace_id, "x").ljust(32, "0")
                ),
                "x-b3-spanid": format(span.context.span_id, "016x"),
                "checked": "baggage"
            }
        )

        carrier = {}
        span = self.tracer().start_span("test_inject")
        span.set_baggage_item("x-b3-flags", 1)
        span.set_baggage_item("x-b3-sampled", 0)
        self.tracer().inject(span.context, Format.HTTP_HEADERS, carrier)
        self.assertEqual(
            carrier,
            {
                "x-b3-traceid": (
                    format(span.context.trace_id, "x").ljust(32, "0")
                ),
                "x-b3-spanid": format(span.context.span_id, "016x"),
                "x-b3-flags": 1,
            }
        )

    def test_extract_multiple_headers(self):

        result = self.tracer().extract(
            Format.HTTP_HEADERS,
            {
                "x-b3-traceid": format(12, "032x"),
                "x-b3-spanid": format(345, "016x"),
                "checked": "baggage"
            }
        )

        self.assertEqual(12, result.trace_id)
        self.assertEqual(345, result.span_id)
        self.assertEqual({"checked": "baggage"}, result.baggage)

        result = self.tracer().extract(
            Format.HTTP_HEADERS,
            {
                "x-b3-traceid": format(12, "032x"),
                "x-b3-spanid": format(345, "016x"),
                "x-b3-flags": 1,
                "x-b3-sampled": 0
            }
        )

        self.assertEqual(12, result.trace_id)
        self.assertEqual(345, result.span_id)
        self.assertEqual({"x-b3-flags": 1}, result.baggage)

    def test_extract_single_header(self):
        result = self.tracer().extract(
            Format.HTTP_HEADERS,
            {
                "b3": "a12-b34-1-c56",
                "checked": "baggage"
            }
        )
        self.assertEqual(2578, result.trace_id)
        self.assertEqual(2868, result.span_id)
        self.assertDictEqual(
            {
                "x-b3-sampled": 1,
                "x-b3-parentspanid": 3158,
                "checked": "baggage"
            },
            result.baggage
        )

        result = self.tracer().extract(
            Format.HTTP_HEADERS,
            {
                "b3": "a12-b34-d-c56",
                "checked": "baggage"
            }
        )
        self.assertEqual(2578, result.trace_id)
        self.assertEqual(2868, result.span_id)
        self.assertDictEqual(
            {
                "x-b3-flags": 1,
                "x-b3-parentspanid": 3158,
                "checked": "baggage"
            },
            result.baggage
        )

    def test_invalid_traceid_spanid(self):

        with raises(SpanContextCorruptedException):
            self.tracer().extract(
                Format.HTTP_HEADERS,
                {
                    "x-b3-spanid": format(345, "016x"),
                    "checked": "baggage"
                }
            )

        with raises(SpanContextCorruptedException):
            self.tracer().extract(
                Format.HTTP_HEADERS,
                {
                    "x-b3-traceid": format(345, "032x"),
                    "checked": "baggage"
                }
            )
