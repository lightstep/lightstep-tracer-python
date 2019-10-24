from re import match, findall, escape
from random import choice
from warnings import warn
from logging import getLogger
from collections import OrderedDict

from basictracer.propagator import Propagator
from basictracer.context import SpanContext
from opentracing import SpanContextCorruptedException

_LOG = getLogger(__name__)

# https://www.w3.org/TR/2019/CR-trace-context-20190813/#header-name
_TRACEPARENT = "traceparent"
_TRACESTATE = "tracestate"


class TraceContextPropagator(Propagator):
    """
    Propagator for the W3C Trace Context format

    The latest version of this Candidate Recommendation can be found here:
    https://www.w3.org/TR/trace-context/

    This is an implementation for this specific version:
    https://www.w3.org/TR/2019/CR-trace-context-20190813/

    The Candidate Recommendation will be referred to as "the document" in the
    comments of this implementation. This implementation adds comments which
    are URLs that point to the specific part of the document that explain the
    rationale of the code that follows the comment.
    """

    def inject(self, span_context, carrier):

        baggage = span_context.baggage
        carrier.update(baggage)

        carrier[_TRACEPARENT] = "00-{}-{}-{}".format(
            span_context.trace_id,
            span_context.span_id,
            "01" if baggage.get("trace_flags", False) else "00"
        )

        if hasattr(span_context, "_tracestate"):

            carrier[_TRACESTATE] = ",".join(
                [
                    "=".join(
                        [key, value] for key, value in
                        span_context._tracestate.items()
                    )
                ]
            )

    def extract(self, carrier):

        traceparent = None
        tracestate = None

        multiple_header_template = "Found more than one header value for {}"

        # FIXME Define more specific exceptions and use them instead of the
        # generic ones that are being raised below

        # https://www.w3.org/TR/2019/CR-trace-context-20190813/#header-name

        trace_context_free_carrier = {}

        for key, value in carrier.items():

            lower_key = key.lower()

            # The document requires that the headers be accepted regardless of
            # the case of their characters. This means that the keys of carrier
            # may contain 2 or more strings that match traceparent or
            # tracestate when the case of the characters of such strings is
            # ignored. The document does not specify what is to be done in such
            # a situation, this implementation will raise an exception.
            # FIXME should this be reported to the W3C Trace Context team?
            if lower_key == _TRACEPARENT:

                if traceparent is None:
                    traceparent = value

                else:
                    raise Exception(
                        multiple_header_template.format(_TRACEPARENT)
                    )

            if lower_key == _TRACESTATE:

                if tracestate is None:
                    tracestate = value

                else:
                    raise Exception(
                        multiple_header_template.format(_TRACEPARENT)
                    )

            trace_context_free_carrier[key] = value

        if traceparent is None:
            # https://www.w3.org/TR/trace-context/#no-traceparent-received
            version = "00"
            trace_id = "".join([choice("abcdef0123456789") for _ in range(16)])
            parent_id = "".join(
                [choice("abcdef0123456789") for _ in range(16)]
            )
            trace_flags = None

            tracestate = None

        else:
            # https://www.w3.org/TR/trace-context/#a-traceparent-is-received

            hexdigitlower = r"[abcdef\d]"

            # https://www.w3.org/TR/2019/CR-trace-context-20190813/#version
            # https://www.w3.org/TR/2019/CR-trace-context-20190813/#version-format
            version_remainder_match = match(
                r"(?P<version>{}{{2}})-"
                r"(?P<remainder>.*)"
                .format(hexdigitlower),
                traceparent
            )

            if version_remainder_match is None:
                _LOG.warning(
                    "Unable to parse version from traceparent,"
                    " restarting trace"
                )
                # https://www.w3.org/TR/2019/CR-trace-context-20190813/#versioning-of-traceparent
                return SpanContext(
                    trace_id=int(
                        "".join(
                            [choice("abcdef0123456789") for _ in range(16)]
                        ),
                        16
                    ),
                    span_id=int(
                        "".join(
                            [choice("abcdef0123456789") for _ in range(16)]
                        ),
                        16
                    ),
                )

            # https://www.w3.org/TR/2019/CR-trace-context-20190813/#version
            version = version_remainder_match.group("version")
            if version == "ff":
                raise SpanContextCorruptedException(
                    "Forbidden value of 255 found in version"
                )

            remainder_match = match(
                (
                    r"(?P<trace_id>{0}{{1,32}})-"
                    r"(?P<parent_id>{0}{{16}})-"
                    r"(?P<trace_flags>{0}{{2}})"
                ).format(hexdigitlower),
                version_remainder_match.group("remainder")
            )

            if remainder_match is None:
                # This will happen if any of the trace-id, parent-id or
                # trace-flags fields contains non-allowed characters.
                # The document specifies that traceparent must be ignored if
                # these kind of characters appear in trace-id and parent-id,
                # but it does not specify what to do if they appear in
                # trace-flags.
                # Here it is assumed that traceparent is to be ignored also if
                # non-allowed characters are present in trace-flags too.
                # FIXME confirm this assumption
                raise SpanContextCorruptedException(
                    "Received an invalid traceparent: {}".format(traceparent)
                )

            # https://www.w3.org/TR/2019/CR-trace-context-20190813/#trace-id
            trace_id = remainder_match.group("trace_id")
            if trace_id == 32 * "0":
                raise SpanContextCorruptedException(
                    "Forbidden value of {} found in trace-id".format(trace_id)
                )

            trace_id_extra_characters = len(trace_id) - 16

            # FIXME The code inside this if and its corresponding elif needs to
            # be confirmed. There is still discussion regarding how trace-id is
            # to be handled in the document.
            if trace_id_extra_characters > 0:
                _LOG.debug(
                    "Truncating {} extra characters from trace-id"
                    .format(trace_id_extra_characters)
                )

                trace_id = trace_id[trace_id_extra_characters:]

            elif trace_id_extra_characters < 0:
                _LOG.debug(
                    "Padding {} extra left zeroes in trace-id"
                    .format(trace_id_extra_characters)
                )

                trace_id = "".join(
                    ["0" * abs(trace_id_extra_characters), trace_id]
                )

            # https://www.w3.org/TR/2019/CR-trace-context-20190813/#parent-id
            parent_id = remainder_match.group("parent_id")
            if parent_id == 16 * "0":
                raise SpanContextCorruptedException(
                    "Forbidden value of {}"
                    " found in parent-id".format(parent_id)
                )

            # https://www.w3.org/TR/2019/CR-trace-context-20190813/#trace-flags
            raw_trace_flags = remainder_match.group("trace_flags")

            trace_flags = {}

            for index, bit_flag in enumerate(
                zip(
                    bin(int(raw_trace_flags, 16))[2:].zfill(8),
                    # https://www.w3.org/TR/2019/CR-trace-context-20190813/#other-flags
                    # Flags can be added in the next list as the document
                    # progresses and they get defined.
                    [None, None, None, None, None, None, None, "sampled"]
                )
            ):
                bit, flag = bit_flag

                if int(bit):
                    if flag is None:
                        warn("Invalid flag set at bit {}".format(index))

                    else:
                        trace_flags[flag] = True

                else:
                    trace_flags[flag] = False

        # https://www.w3.org/TR/2019/CR-trace-context-20190813/#tracestate-header
        # As the document indicates in the URL before, failure to parse
        # traceparent must stop the parsing of tracestate. This stoppage is
        # achieved here by raising SpanContextCorruptedException when one of
        # these parsing failures is found.

        # https://www.w3.org/TR/2019/CR-trace-context-20190813/#key
        key_re = (
            r"[{0}][-{0}/d_*/]{{0,255}}|"
            r"[{0}/d][-{0}/d_*/]{{0,240}}@{0}[-{0}/d_*/]{{0,13}}"
        ).format(
            escape(r"".join([chr(character) for character in range(97, 123)]))
        )

        # https://www.w3.org/TR/2019/CR-trace-context-20190813/#value
        value_re = r"( |[{0}]){{0,255}}[{0}]".format(
            escape(
                r"".join(
                    [
                        chr(character) for character in range(33, 127)
                        if character not in [44, 61]
                    ]
                )
            )
        )

        trace_context_free_carrier.update(trace_flags)

        span_context = SpanContext(
            trace_id=int(trace_id, 16),
            span_id=int(parent_id, 16),
            baggage=trace_context_free_carrier
        )

        if tracestate is not None:
            tracestate_match = match(
                # https://www.w3.org/TR/2019/CR-trace-context-20190813/#list
                r"{0}={1}| *( *, *({0}={1}| *)){{0,31}}"
                .format(key_re, value_re),
                tracestate
            )

            if tracestate_match is None:
                warn("Invalid tracestate found: {}".format(tracestate))

            else:
                tracestate = OrderedDict()

                for key, value in findall(
                    r"({0})=({1}))".format(key_re, value_re), tracestate
                ):

                    tracestate[key] = value

                span_context._tracestate = tracestate

        return span_context
