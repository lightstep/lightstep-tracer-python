from __future__ import absolute_import

import base64
import time
import struct
from opentracing import InvalidCarrierException, TraceCorruptedException
from .context import Context
from .span import BasicSpan
from .wire_pb2 import TracerState
from .util import generate_id

_proto_size_bytes = 4 # bytes

class BinaryPropagator(object):
    def __init__(self, tracer):
        self.tracer = tracer

    def inject(self, span, carrier):
        if type(carrier) is not bytearray:
            raise InvalidCarrierException()
        state = TracerState()
        state.trace_id = span.context.trace_id
        state.span_id = span.context.span_id
        state.sampled = span.context.sampled
        if span.context.baggage is not None:
            for key in span.context.baggage:
                state.baggage_items[key] = span.context.baggage[key]

        # The binary format is {uint32}{protobuf} using big-endian for the uint
        carrier.extend(struct.pack(">I", state.ByteSize()))
        carrier.extend(state.SerializeToString())

    def join(self, operation_name, carrier):
        if type(carrier) is not bytearray:
            raise InvalidCarrierException()
        state = TracerState()
        state.ParseFromString(str(carrier[_proto_size_bytes:]))
        baggage = {}
        for k in state.baggage_items:
            baggage[k] = state.baggage_items[k]

        return BasicSpan(self.tracer,
                operation_name=operation_name,
                start_time=time.time(),
                context=Context(span_id=generate_id(),
                    parent_id=state.span_id,
                    trace_id=state.trace_id,
                    baggage=baggage,
                    sampled=state.sampled))


prefix_tracer_state = 'ot-tracer-'
prefix_baggage = 'ot-baggage-'
field_name_trace_id = prefix_tracer_state + 'traceid'
field_name_span_id = prefix_tracer_state + 'spanid'
field_name_sampled = prefix_tracer_state + 'sampled'
field_count = 3

class TextPropagator(object):
    def __init__(self, tracer):
        self.tracer = tracer

    def inject(self, span, carrier):
        carrier[field_name_trace_id] = '{:x}'.format(span.context.trace_id)
        carrier[field_name_span_id] = '{:x}'.format(span.context.span_id)
        carrier[field_name_sampled] = str(span.context.sampled).lower()
        if span.context.baggage is not None:
            for k in span.context.baggage:
                carrier[prefix_baggage+k] = span.context.baggage[k]

    def join(self, operation_name, carrier):
        count = 0
        span_id, trace_id, sampled = (0, 0, False)
        baggage = {}
        for k in carrier:
            v = carrier[k]
            k = k.lower()
            if k == field_name_span_id:
                span_id = int(v, 16)
                count += 1
            elif k == field_name_trace_id:
                trace_id = int(v, 16)
                count += 1
            elif k == field_name_sampled:
                if v == str(True).lower():
                    sampled = True
                elif v == str(False).lower():
                    sampled = False
                else:
                    raise TraceCorruptedException()
                count += 1
            elif k.startswith(prefix_baggage):
                baggage[k[len(prefix_baggage):]] = v

        if count != field_count:
            raise TraceCorruptedException()

        return BasicSpan(self.tracer,
                operation_name=operation_name,
                start_time=time.time(),
                context=Context(span_id=generate_id(),
                    parent_id=span_id,
                    trace_id=trace_id,
                    baggage=baggage,
                    sampled=sampled))
