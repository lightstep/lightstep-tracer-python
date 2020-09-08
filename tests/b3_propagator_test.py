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
                "x-b3-traceid": format(span.context.trace_id, "x"),
                "x-b3-spanid": format(span.context.span_id, "x"),
                "x-b3-sampled": "1",
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
                "x-b3-traceid": format(span.context.trace_id, "x"),
                "x-b3-spanid": format(span.context.span_id, "x"),
                "x-b3-flags": "1",
            }
        )

    def test_extract_multiple_headers(self):

        result = self.tracer().extract(
            Format.HTTP_HEADERS,
            {
                "x-b3-traceid": format(12, "x"),
                "x-b3-spanid": format(345, "x"),
                "checked": "baggage"
            }
        )

        self.assertEqual(12, result.trace_id)
        self.assertEqual(345, result.span_id)
        self.assertEqual({"checked": "baggage"}, result.baggage)

        result = self.tracer().extract(
            Format.HTTP_HEADERS,
            {
                "x-b3-traceid": format(12, "x"),
                "x-b3-spanid": format(345, "x"),
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
                    "x-b3-spanid": format(345, "x"),
                    "checked": "baggage"
                }
            )

        with raises(SpanContextCorruptedException):
            self.tracer().extract(
                Format.HTTP_HEADERS,
                {
                    "x-b3-traceid": format(345, "x"),
                    "checked": "baggage"
                }
            )

    def test_propagation(self):

        tracer = self.tracer()

        def test_attribute(attribute_name, attribute_value):
            inject_span = tracer.start_span("test_propagation")
            setattr(
                inject_span.context, attribute_name, int(attribute_value, 16)
            )

            carrier = {}
            tracer.inject(inject_span.context, Format.HTTP_HEADERS, carrier)

            self.assertEqual(
                carrier["x-b3-{}".format(attribute_name.replace("_", ""))],
                attribute_value
            )

            extract_span_context = tracer.extract(Format.HTTP_HEADERS, carrier)

            self.assertEqual(
                getattr(inject_span.context, attribute_name),
                getattr(extract_span_context, attribute_name)
            )

        test_attribute("trace_id", "ef5705a090040838f1359ebafa5c0c6")
        test_attribute("trace_id", "ef5705a09004083")
        test_attribute("span_id", "aef5705a09004083")

        def test_sampled(sampled_value):

            inject_span = tracer.start_span("test_propagation")
            inject_span.context.baggage["x-b3-sampled"] = sampled_value

            carrier = {}
            tracer.inject(inject_span.context, Format.HTTP_HEADERS, carrier)

            self.assertTrue(isinstance(carrier["x-b3-sampled"], str))

            extract_span_context = tracer.extract(Format.HTTP_HEADERS, carrier)

            self.assertEqual(
                carrier["x-b3-sampled"],
                extract_span_context.baggage["x-b3-sampled"]
            )

        test_sampled(True)
        test_sampled(False)
        test_sampled(1)
        test_sampled(0)

        inject_span = tracer.start_span("test_propagation")

        self.assertTrue(
            "x-b3-sampled" not in inject_span.context.baggage.keys()
        )

        carrier = {}

        tracer.inject(inject_span.context, Format.HTTP_HEADERS, carrier)

        self.assertEqual(carrier["x-b3-sampled"], "1")

        extract_span_context = tracer.extract(Format.HTTP_HEADERS, carrier)

        self.assertEqual(
            carrier["x-b3-sampled"],
            extract_span_context.baggage["x-b3-sampled"]
        )
