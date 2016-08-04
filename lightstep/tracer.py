"""
LightStep's implementation of the python OpenTracing API.

http://opentracing.io
https://github.com/opentracing/api-python

See the API definition for comments.
"""
from __future__ import absolute_import

from basictracer import BasicTracer
from basictracer.text_propagator import TextPropagator
from opentracing import Format

from .recorder import Recorder, LoggingRecorder

_TRACER_STATE_PREFIX = "ot-tracer-"
_BAGGAGE_PREFIX = "ot-baggage-"
_BAGGAGE_PREFIX_LEN = len(_BAGGAGE_PREFIX)
_FIELD_NAME_TRACE_GUID = 'traceid'
_FIELD_NAME_SPAN_GUID = 'spanid'
_FIELD_NAME_SAMPLED = 'sampled'
""" Note that these strings are lowercase because HTTP headers mess with capitalization.
"""

def init_tracer(**kwargs):
    """Instantiates LightStep's OpenTracing implementation.

    :param str group_name: name identifying the type of service that is being tracked
    :param str access_token: project's access token
    :param bool secure: whether HTTP connection is secure
    :param str service_host: Service host name
    :param int service_port: Service port number
    :param int max_span_records: Maximum number of spans records to buffer
    :param int periodic_flush_seconds: seconds between periodic flushes, or 0
        to disable
    :param bool disable_binary_format: Whether to disable the binary
        inject/extract format (which relies on protobufs and may cause problems
        if other versions of protobufs are active in the same packaging
        configuration). Defaults to False (i.e., binary format is enabled).
    """
    enable_binary_format = True
    if kwargs.has_key('disable_binary_format'):
        enable_binary_format = not kwargs['disable_binary_format']
        del kwargs['disable_binary_format']
    return _LightstepTracer(enable_binary_format, Recorder(**kwargs))


def init_debug_tracer():
    """Returns a tracer that logs to the console instead of reporting to
    LightStep."""
    tracer = BasicTracer(LoggingRecorder())
    tracer.register_required_propagators()
    return tracer


class _LightstepTracer(BasicTracer):
    def __init__(self, enable_binary_format, recorder):
        """Initialize the LightStep Tracer, deferring to BasicTracer."""
        super(_LightstepTracer, self).__init__(recorder)
        self.register_propagator(Format.TEXT_MAP, TextPropagator())
        self.register_propagator(Format.HTTP_HEADERS, TextPropagator())
        if enable_binary_format:
            # We do this import lazily because protobuf versioning issues
            # can cause process-level failure at import time.
            from basictracer.binary_propagator import BinaryPropagator
            self.register_propagator(Format.BINARY, BinaryPropagator())

    def flush(self):
        """Force a flush of buffered Span data to the LightStep collector."""
        self.recorder.flush()
