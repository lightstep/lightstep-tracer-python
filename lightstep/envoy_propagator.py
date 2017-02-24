from __future__ import absolute_import

from base64 import standard_b64decode
from base64 import standard_b64encode
from basictracer.context import SpanContext
from basictracer.propagator import Propagator
# This can cause problems when old versions of protobuf are installed
from opentracing import InvalidCarrierException

from lightstep.envoy_carrier_pb2 import EnvoyCarrier


class EnvoyPropagator(Propagator):
    """A BasicTracer Propagator for LightStepFormat.ENVOY_HEADERS."""

    def inject(self, span_context, carrier):
        if type(carrier) is not bytearray:
            raise InvalidCarrierException()
        state = EnvoyCarrier()
        state.trace_id = span_context.trace_id
        state.span_id = span_context.span_id
        state.sampled = span_context.sampled
        if span_context.baggage is not None:
            for key in span_context.baggage:
                state.baggage_items[key] = span_context.baggage[key]

        serializedProto = state.SerializeToString()
        carrier.extend(standard_b64encode(serializedProto))

    def extract(self, carrier):
        if type(carrier) is not bytearray:
            raise InvalidCarrierException()
        serializedProto = standard_b64decode(carrier)
        state = EnvoyCarrier()
        state.ParseFromString(str(serializedProto))
        baggage = {}
        for k in state.baggage_items:
            baggage[k] = state.baggage_items[k]

        return SpanContext(
            span_id=state.span_id,
            trace_id=state.trace_id,
            baggage=baggage,
            sampled=state.sampled)