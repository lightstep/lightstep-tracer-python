from __future__ import absolute_import

from base64 import standard_b64decode
from base64 import standard_b64encode
from basictracer.context import SpanContext
from basictracer.propagator import Propagator
# This can cause problems when old versions of protobuf are installed
from opentracing import InvalidCarrierException

from lightstep.lightstep_carrier_pb2 import BinaryCarrier
from lightstep.lightstep_carrier_pb2 import BasicTracerCarrier


class LightStepBinaryPropagator(Propagator):
    """A BasicTracer Propagator for LightStepFormat.LIGHTSTEP_BINARY."""

    def inject(self, span_context, carrier):
        if type(carrier) is not bytearray:
            raise InvalidCarrierException()

        state = BinaryCarrier()
        basic_ctx = state.basic_ctx

        basic_ctx.trace_id = span_context.trace_id
        basic_ctx.span_id = span_context.span_id
        basic_ctx.sampled = span_context.sampled
        if span_context.baggage is not None:
            for key in span_context.baggage:
                basic_ctx.baggage_items[key] = span_context.baggage[key]


        serializedProto = state.SerializeToString()
        encoded = standard_b64encode(serializedProto)
        carrier.extend(encoded)

    def extract(self, carrier):
        if type(carrier) is not bytearray:
            raise InvalidCarrierException()
        serializedProto = standard_b64decode(carrier)
        state = BinaryCarrier()
        state.ParseFromString(bytes(serializedProto))
        baggage = {}
        for k in state.basic_ctx.baggage_items:
            baggage[k] = state.basic_ctx.baggage_items[k]

        return SpanContext(
            span_id=state.basic_ctx.span_id,
            trace_id=state.basic_ctx.trace_id,
            baggage=baggage,
            sampled=state.basic_ctx.sampled)
