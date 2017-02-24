from __future__ import absolute_import

import struct
from basictracer.context import SpanContext
from basictracer.propagator import Propagator
# This can cause problems when old versions of protobuf are installed
from opentracing import InvalidCarrierException

from lightstep.envoy_carrier_pb2 import EnvoyCarrier

_proto_size_bytes = 4  # bytes


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

        # The binary format is {uint32}{protobuf} using big-endian for the uint
        carrier.extend(struct.pack('>I', state.ByteSize()))
        carrier.extend(state.SerializeToString())

    def extract(self, carrier):
        if type(carrier) is not bytearray:
            raise InvalidCarrierException()
        state = EnvoyCarrier()
        state.ParseFromString(str(carrier[_proto_size_bytes:]))
        baggage = {}
        for k in state.baggage_items:
            baggage[k] = state.baggage_items[k]

        return SpanContext(
            span_id=state.span_id,
            trace_id=state.trace_id,
            baggage=baggage,
            sampled=state.sampled)