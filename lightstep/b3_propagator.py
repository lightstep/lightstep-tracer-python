from warnings import warn
from logging import getLogger

from basictracer.propagator import Propagator
from basictracer.context import SpanContext
from opentracing import SpanContext as OTSpanContext
from opentracing import SpanContextCorruptedException

_LOG = getLogger(__name__)
_SINGLE_HEADER = "b3"
# Lower case is used here as the B3 specification recommends
_TRACEID = "x-b3-traceid"
_SPANID = "x-b3-spanid"
_PARENTSPANID = "x-b3-parentspanid"
_SAMPLED = "x-b3-sampled"
_FLAGS = "x-b3-flags"


class B3Propagator(Propagator):
    """
    Propagator for the B3 HTTP header format.

    See: https://github.com/openzipkin/b3-propagation
    """

    def inject(self, span_context, carrier):

        traceid = span_context.trace_id
        spanid = span_context.span_id

        baggage = span_context.baggage

        parentspanid = baggage.pop(_PARENTSPANID, None)
        if parentspanid is not None:
            carrier[_PARENTSPANID] = parentspanid

        flags = baggage.pop(_FLAGS, None)
        if flags is not None:
            carrier[_FLAGS] = flags

        sampled = baggage.pop(_SAMPLED, None)

        if sampled is None:
            carrier[_SAMPLED] = 1
        else:
            if flags == 1:
                _LOG.warning(
                    "x-b3-flags: 1 implies x-b3-sampled: 1, not sending "
                    "the value of x-b3-sampled"
                )
            else:
                if isinstance(sampled, bool):
                    warn(
                        "The value of x-b3-sampled should "
                        "be {} instead of {}".format(
                            int(sampled), sampled
                        )
                    )
                carrier[_SAMPLED] = sampled

        if sampled is flags is (traceid and spanid) is None:
            warn(
                "If not propagating only the sampling state, traceid and "
                "spanid must be defined, setting sampling state to 1."
            )
            carrier[_SAMPLED] = 1

        carrier.update(baggage)

        if traceid is not None:
            carrier[_TRACEID] = format(traceid, "x")
        if spanid is not None:
            carrier[_SPANID] = format(spanid, "x")

    def extract(self, carrier):

        case_insensitive_carrier = {}
        for key, value in carrier.items():
            for b3_key in [
                _SINGLE_HEADER,
                _TRACEID,
                _SPANID,
                _PARENTSPANID,
                _SAMPLED,
                _FLAGS,
            ]:
                if key.lower() == b3_key:
                    case_insensitive_carrier[b3_key] = value
                else:
                    case_insensitive_carrier[key] = value

        carrier = case_insensitive_carrier
        baggage = {}

        if _SINGLE_HEADER in carrier.keys():
            fields = carrier.pop(_SINGLE_HEADER).split("-", 4)
            baggage.update(carrier)
            len_fields = len(fields)
            if len_fields == 1:
                sampled = fields[0]
            elif len_fields == 2:
                traceid, spanid = fields
            elif len_fields == 3:
                traceid, spanid, sampled = fields
            else:
                traceid, spanid, sampled, parent_spanid = fields
                baggage[_PARENTSPANID] = int(parent_spanid, 16)
            if sampled == "d":
                baggage[_FLAGS] = 1
            else:
                baggage[_SAMPLED] = int(sampled, 16)
        else:
            traceid = carrier.pop(_TRACEID, None)
            spanid = carrier.pop(_SPANID, None)
            parentspanid = carrier.pop(_PARENTSPANID, None)
            sampled = carrier.pop(_SAMPLED, None)
            flags = carrier.pop(_FLAGS, None)

            if sampled is flags is (traceid and spanid) is None:

                raise SpanContextCorruptedException()

            if parentspanid is not None:
                baggage[_PARENTSPANID] = int(parentspanid, 16)

            if flags == 1:
                baggage[_FLAGS] = flags
                if sampled is not None:
                    warn(
                        "x-b3-flags: 1 implies x-b3-sampled: 1, ignoring "
                        "the received value of x-b3-sampled"
                    )
            elif sampled is not None:
                baggage[_SAMPLED] = sampled

            baggage.update(carrier)

            if baggage == OTSpanContext.EMPTY_BAGGAGE:
                baggage = None

        return SpanContext(
            trace_id=int(traceid, 16),
            span_id=int(spanid, 16),
            baggage=baggage
        )
