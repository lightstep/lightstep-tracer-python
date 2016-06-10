"""
LightStep's implementation of the python OpenTracing API.

http://opentracing.io
https://github.com/opentracing/api-python

See the API definition for comments.
"""
from __future__ import absolute_import


import copy
import json
import threading
import time
import traceback
import urllib
import warnings
import sys
import os

import opentracing

from .basictracer import BasicTracer

from .recorder import Recorder, LoggingRecorder
from .util import generate_id, _now_micros


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


# class BasicTracer(Tracer):

#     def __init__(self, recorder=None, sampler=None):
#         self.recorder = NoopRecorder() if recorder is None else recorder
#         self.sampler = DefaultSampler(1) if sampler is None else sampler
#         self._binary_propagator = BinaryPropagator(self)
#         self._text_propagator = TextPropagator(self)
#         self._runtime_guid = recorder._runtime_guid
#         return

#     def start_span(self,
#             operation_name=None,
#             parent=None,
#             tags=None,
#             start_time=None):
#         start_time = _now_micros() if start_time is None else start_time
#         context = Context(span_id=generate_id())
#         sp = BasicSpan(self, operation_name=operation_name, tags=tags,
#                 context=context,
#                 start_time=start_time)

#         if parent is None:
#             sp.context.trace_id = generate_id()
#             sp.context.sampled = self.sampler.sampled(sp.context.trace_id)
#         else:
#             sp.context.trace_id = parent.context.trace_id
#             sp.context.parent_id = parent.context.span_id
#             sp.context.sampled = parent.context.sampled
#             if parent.context.baggage is not None:
#                 sp.context.baggage = parent.context.baggage.copy()

#         return sp


#     def inject(self, span, format, carrier):
#         if format == Format.BINARY:
#             self._binary_propagator.inject(span, carrier)
#         elif format == Format.TEXT_MAP:
#             self._text_propagator.inject(span, carrier)
#         else:
#             raise UnsupportedFormatException()

#     def join(self, operation_name, format, carrier):
#         if format == Format.BINARY:
#             return self._binary_propagator.join(operation_name, carrier)
#         elif format == Format.TEXT_MAP:
#             return self._text_propagator.join(operation_name, carrier)
#         else:
#             raise UnsupportedFormatException()
    
#     def record(self, span):
#         self.recorder.record_span(span)

#     def flush(self):
#         return self.recorder.flush()

# class NoopRecorder(SpanRecorder):
#     def record_span(self, span):
#         pass    
