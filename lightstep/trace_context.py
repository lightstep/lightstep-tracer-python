from re import escape, compile as re_compile
from random import getrandbits
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

# https://www.w3.org/TR/trace-context/#a-traceparent-is-received
_HEXDIGITLOWER = r"[abcdef\d]"

# https://www.w3.org/TR/2019/CR-trace-context-20190813/#version
# https://www.w3.org/TR/2019/CR-trace-context-20190813/#version-format
_VERSION = re_compile(r"\s*(?P<version>{0}{{2}})-".format(_HEXDIGITLOWER))

# https://www.w3.org/TR/trace-context/#trace-id
# https://www.w3.org/TR/trace-context/#parent-id
# https://www.w3.org/TR/trace-context/#trace-flags
_REMAINDER_MATCH_RE = (
    r"{0}{{2}}-"
    r"(?P<trace_id>{0}{{32}})-"
    r"(?P<parent_id>{0}{{16}})-"
    r"(?P<trace_flags>{0}{{2}})"
).format(_HEXDIGITLOWER)

# https://www.w3.org/TR/2019/CR-trace-context-20190813/#versioning-of-traceparent
_00_VERSION_REMAINDER = re_compile("".join([_REMAINDER_MATCH_RE, r"\s*$"]))
_FUTURE_VERSION_REMAINDER = re_compile(
    "".join([_REMAINDER_MATCH_RE, r"(\s*$|-[^\s]+)"])
)

_KEY_VALUE = re_compile(
    r"^\s*({0})=({1})\s*$".format(
        # https://www.w3.org/TR/2019/CR-trace-context-20190813/#tracestate-header
        # https://www.w3.org/TR/2019/CR-trace-context-20190813/#key
        (
            r"[{0}][-{0}\d_*/]{{0,255}}|"
            r"[{0}\d][-{0}\d_*/]{{0,240}}@[{0}][-{0}\d_*/]{{0,13}}"
        ).format("a-z"),
        # https://www.w3.org/TR/2019/CR-trace-context-20190813/#value
        r"[ {0}]{{0,255}}[{0}]".format(
            escape(
                r"".join(
                    [
                        chr(character) for character in range(33, 127)
                        if character not in [44, 61]
                    ]
                )
            )
        )
    )
)

_BLANK = re_compile(r"^\s*$")


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

    There is a set of test cases defined for testing any implementation of the
    document. This set of test cases can be found here:
    https://github.com/w3c/trace-context/tree/master/test

    This set of test cases will be referred to as "the test suite" in the
    comments of this implementation.
    """

    def inject(self, span_context, carrier):

        carrier[_TRACEPARENT] = "00-{}-{}-{}".format(
            format(span_context.trace_id, "032x"),
            format(span_context.span_id, "016x"),
            format(span_context.baggage.pop("trace-flags", 0), "02x")
        )

        carrier.update(span_context.baggage)

    def extract(self, carrier):
        traceparent = None
        tracestate = None

        multiple_header_template = "Found more than one header value for {}"

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
            if lower_key == _TRACEPARENT:

                if traceparent is None:
                    traceparent = value

                else:
                    raise SpanContextCorruptedException(
                        multiple_header_template.format(_TRACEPARENT)
                    )

            elif lower_key == _TRACESTATE:

                if tracestate is None:
                    tracestate = value

                else:
                    raise SpanContextCorruptedException(
                        multiple_header_template.format(_TRACEPARENT)
                    )

            else:
                trace_context_free_carrier[key] = value

        if traceparent is None:
            # https://www.w3.org/TR/trace-context/#no-traceparent-received
            _LOG.warning("No traceparent was received")
            return SpanContext(
                trace_id=getrandbits(128), span_id=getrandbits(64)
            )

        else:

            version_match = _VERSION.match(traceparent)

            if version_match is None:
                # https://www.w3.org/TR/2019/CR-trace-context-20190813/#versioning-of-traceparent
                _LOG.warning(
                    "Unable to parse version from traceparent"
                )
                return SpanContext(
                    trace_id=getrandbits(128), span_id=getrandbits(64)
                )

            # https://www.w3.org/TR/2019/CR-trace-context-20190813/#version
            version = version_match.group("version")
            if version == "ff":
                _LOG.warning(
                    "Forbidden value of 255 found in version"
                )
                return SpanContext(
                    trace_id=getrandbits(128), span_id=getrandbits(64)
                )

            # https://www.w3.org/TR/2019/CR-trace-context-20190813/#versioning-of-traceparent
            if int(version, 16) > 0:

                if len(traceparent) < 55:
                    _LOG.warning(
                        "traceparent shorter than 55 characters found"
                    )
                    return SpanContext(
                        trace_id=getrandbits(128), span_id=getrandbits(64)
                    )

                remainder_match = _FUTURE_VERSION_REMAINDER.match(traceparent)

            else:
                remainder_match = _00_VERSION_REMAINDER.match(traceparent)

            if remainder_match is None:
                # This will happen if any of the trace-id, parent-id or
                # trace-flags fields contains non-allowed characters.
                # The document specifies that traceparent must be ignored if
                # these kind of characters appear in trace-id and parent-id,
                # but it does not specify what to do if they appear in
                # trace-flags.
                # Here it is assumed that traceparent is to be ignored also if
                # non-allowed characters are present in trace-flags too.
                _LOG.warning(
                    "Received an invalid traceparent: {}".format(traceparent)
                )
                return SpanContext(
                    trace_id=getrandbits(128), span_id=getrandbits(64)
                )

            # https://www.w3.org/TR/2019/CR-trace-context-20190813/#trace-id
            trace_id = remainder_match.group("trace_id")
            if trace_id == 32 * "0":
                _LOG.warning(
                    "Forbidden value of {} found in trace-id".format(trace_id)
                )
                return SpanContext(
                    trace_id=getrandbits(128), span_id=getrandbits(64)
                )

            # https://www.w3.org/TR/2019/CR-trace-context-20190813/#parent-id
            parent_id = remainder_match.group("parent_id")
            if parent_id == 16 * "0":
                _LOG.warning(
                    "Forbidden value of {}"
                    " found in parent-id".format(parent_id)
                )
                return SpanContext(
                    trace_id=getrandbits(128), span_id=getrandbits(64)
                )

            # https://www.w3.org/TR/2019/CR-trace-context-20190813/#trace-flags
            raw_trace_flags = remainder_match.group("trace_flags")

            trace_flags = []

            for index, bit_flag in enumerate(
                zip(
                    bin(int(raw_trace_flags, 16))[2:].zfill(8),
                    # https://www.w3.org/TR/2019/CR-trace-context-20190813/#other-flags
                    # Flags can be added in the next list as the document
                    # progresses and they get defined. This list represents the
                    # 8 bits that are available in trace-flags and their
                    # respective meaning.
                    [None, None, None, None, None, None, None, "sampled"]
                )
            ):
                bit, flag = bit_flag

                if int(bit):
                    if flag is None:
                        warn("Invalid flag set at bit {}".format(index))
                        trace_flags.append("0")

                    else:
                        trace_flags.append("1")

                else:
                    trace_flags.append("0")

            trace_context_free_carrier["trace-flags"] = int(
                "".join(trace_flags), 2
            )

            if tracestate is not None:

                tracestate_dictionary = OrderedDict()

                for counter, list_member in enumerate(tracestate.split(",")):
                    # https://www.w3.org/TR/trace-context/#tracestate-header-field-values
                    if counter > 31:
                        _LOG.warning(
                            "More than 32 list-members "
                            "found in tracestate {}".format(tracestate)
                        )
                        break

                    # https://www.w3.org/TR/trace-context/#tracestate-header-field-values
                    if _BLANK.match(list_member):
                        _LOG.debug(
                            "Ignoring empty tracestate list-member"
                        )
                        continue

                    key_value = _KEY_VALUE.match(list_member)

                    if key_value is None:
                        _LOG.warning(
                            "Invalid key/value pair found: {}".format(
                                key_value
                            )
                        )
                        break

                    key, value = key_value.groups()

                    if key in tracestate_dictionary.keys():
                        _LOG.warning(
                            "Duplicate tracestate key found: {}".format(key)
                        )
                        break

                    tracestate_dictionary[key] = value

                else:
                    trace_context_free_carrier[_TRACESTATE] = ",".join(
                        [
                            "{0}={1}".format(key, value)
                            for key, value in tracestate_dictionary.items()
                        ]
                    )

        return SpanContext(
            trace_id=int(trace_id, 16),
            span_id=int(parent_id, 16),
            baggage=trace_context_free_carrier
        )
