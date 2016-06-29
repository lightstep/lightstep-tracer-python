"""
LightStep's implementation of the python OpenTracing API.

http://opentracing.io
https://github.com/opentracing/api-python

See the API definition for comments.
"""
from __future__ import absolute_import

from basictracer import BasicTracer

from .recorder import Recorder, LoggingRecorder

_TRACER_STATE_PREFIX = "ot-tracer-"
_BAGGAGE_PREFIX = "ot-baggage-"
_BAGGAGE_PREFIX_LEN = len(_BAGGAGE_PREFIX)
_FIELD_NAME_TRACE_GUID = 'traceid'
_FIELD_NAME_SPAN_GUID = 'spanid'
_FIELD_NAME_SAMPLED = 'sampled'
""" Note that these strings are lowercase because HTTP headers mess with capitalization.
"""

def init_tracer(*args, **kwargs):
    """Instantiates LightStep's OpenTracing implementation.

    :param str group_name: name identifying the type of service that is being tracked
    :param str access_token: project's access token
    :param bool secure: whether HTTP connection is secure
    :param str service_host: Service host name
    :param int service_port: Service port number
    :param int max_log_records: Maximum number of log records to buffer
    :param int max_span_records: Maximum number of spans records to buffer
    :param int periodic_flush_seconds: seconds between periodic flushes, or 0
        to disable
    """
    return BasicTracer(Recorder(*args, **kwargs))


def init_debug_tracer():
    """Returns a tracer that logs to the console instead of reporting to
    LightStep."""
    return BasicTracer(LoggingRecorder())
