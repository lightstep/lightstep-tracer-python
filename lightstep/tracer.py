"""
LightStep's implementation of the python OpenTracing API.

http://opentracing.io
https://github.com/opentracing/api-python

See the API definition for comments.
"""

import copy
import json
import threading
import time
import traceback
import urllib
import warnings

import opentracing

from .crouton import ttypes
from . import constants, reporter as reporter_module, util


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
    return Tracer(reporter_module.LightStepReporter(*args, **kwargs))


def init_debug_tracer():
    """Returns a tracer that logs to the console instead of reporting to
    LightStep."""
    return Tracer(reporter_module.LoggingReporter())

class Span(opentracing.Span):
    """A LightStep implementation of opentracing.Span."""

    def __init__(self, operation_name, tracer, parent=None, tags=None, start_time=None):

        super(Span, self).__init__(tracer)

        # Set up the tracer state and baggage.
        if parent is None:
            self.trace_guid = util._generate_guid()
            self.parent_guid = 0
            self.span_guid = util._generate_guid()
            self.baggage = {}
        else:
            self.trace_guid = str(parent.trace_guid)
            self.parent_guid = str(parent.span_guid)
            self.span_guid = util._generate_guid()
            self.baggage = copy.deepcopy(parent.baggage)

        self.logs = []
        if start_time is None:
            oldest_micros = util._now_micros()
        else:
            oldest_micros = util._time_to_micros(start_time)

        # Thrift is picky about the types being right, so be explicit here
        self.span_record = ttypes.SpanRecord(
            trace_guid=str(self.trace_guid),
            span_guid=str(self.span_guid),
            runtime_guid=str(tracer._runtime_guid),
            span_name=str(operation_name),
            join_ids=[],
            oldest_micros=long(oldest_micros),
            attributes=[],
        )
        if self.parent_guid:
            self.set_tag("parent_span_guid", self.parent_guid)
        if tags:
            for k, v in tags.iteritems():
                self.set_tag(k, v)

    def finish(self):
        self.span_record.youngest_micros = util._now_micros()
        self.tracer._report_span(self)

    def set_operation_name(self, operation_name):
        self.span_record.span_name = operation_name
        return self

    def set_tag(self, key, value):
        if not isinstance(key, basestring):
            warnings.warn('set_tag key must be a string. Tag ignored.', UserWarning, 3)
            return self
        if value == None:
            warning.warn('set_tag value not valid. Tag ignored.', UserWarning, 3)
            return self

        # Coerce the value to a string as the Thrift binary protocol does not
        # accept type-mismatches
        # TODO(jmacd): These and other conversions: can they be done
        # in the background thread?
        value = str(value)

        # TODO(misha): Canonicalize key more thoroughly.
        key = key.lower()
        if key.startswith(self.tracer.join_tag_prefix):
            key = key[len(self.tracer.join_tag_prefix):]
            self._set_join_id(key, value)
        else:
            self._set_attribute(key, value)
        return self

    def _set_join_id(self, key, value):
        trace_join_id = ttypes.TraceJoinId(str(key), str(value))
        self.span_record.join_ids.append(trace_join_id)

    def _set_attribute(self, key, value):
        attribute = ttypes.KeyValue(str(key), str(value))
        self.span_record.attributes.append(attribute)

    def set_baggage_item(self, key, value):
        self.baggage[str(key).lower()] = str(value)
        return self

    def get_baggage_item(self, key):
        canon_key = key.lower()
        return self.baggage.get(canon_key)

    def log_event(self, event, payload=None):
        return self._log_explicit(None, event, payload)

    def log(self, **kwargs):
        return self._log_explicit(kwargs.get("timestamp"),
                                  kwargs.get("event", ""),
                                  kwargs.get("payload"))

    def _log_explicit(self, timestamp, event, payload=None):
        if timestamp == None:
            timestamp = time.time()
        elif not isinstance(timestamp, (float)):
            warnings.warn('Invalid type for timestamp on log. Dropping log. Type:' + str(type(timestamp)), UserWarning, 3)
            return

        log_record = ttypes.LogRecord(
            timestamp_micros=util._time_to_micros(timestamp),
            runtime_guid=str(self.span_record.runtime_guid),
            span_guid=str(self.span_guid),
            level=constants.INFO_LOG,
            error_flag=False,

            # Note: the following two fields are prepared for encoding
            # in the background thread.
            stable_name=event,
            payload_json=payload,
        )

        self.logs.append(log_record)
        return self


class Tracer(object):
    """A LightStep implementation of opentracing.Tracer.

    See init_tracer() and init_debug_tracer().
    """
    def __init__(self, reporter, join_tag_prefix='join:'):
        """Initialize and return a new LightStep Tracer.

        :param reporter: a lightstep.Reporter instance for the collector
            connection.
        :param join_tag_prefix: the string prefix used for LightStep join tags,
            per Span.set_tag().
        """
        self.reporter = reporter
        self._runtime_guid = reporter._runtime_guid
        self.join_tag_prefix = join_tag_prefix.lower()

    def start_span(self,
                   operation_name=None,
                   parent=None,
                   tags=None,
                   start_time=None):
        return Span(operation_name,
                    self,
                    parent=parent,
                    tags=tags,
                    start_time=start_time)

    def inject(self, span, format, carrier):
        if format == opentracing.Format.TEXT_MAP:
            carrier.update({
                _TRACER_STATE_PREFIX + _FIELD_NAME_TRACE_GUID: span.trace_guid,
                _TRACER_STATE_PREFIX + _FIELD_NAME_SPAN_GUID: span.span_guid,
                # basictracer compatibility:
                _TRACER_STATE_PREFIX + _FIELD_NAME_SAMPLED: "true",
                })
            for k, v in span.baggage.iteritems():
                carrier[_BAGGAGE_PREFIX + k] = urllib.quote(v)
            return
        elif format == opentracing.Format.BINARY:
            # TODO: create a basictracer-python impl that uses the .proto
            # encoding from basictracer-go.
            raise NotImplementedError()
        else:
            raise NotImplementedError()

    def join(self, operation_name, format, carrier):
        if format == opentracing.Format.TEXT_MAP:
            decoded_baggage = {}
            for k in carrier:
                if k.lower().startswith(_BAGGAGE_PREFIX):
                    decoded_baggage[k.lower()[_BAGGAGE_PREFIX_LEN:]] = urllib.unquote(carrier.baggage[k])
            duck_parent = type('', (), {
                'trace_guid': carrier[_TRACER_STATE_PREFIX + _FIELD_NAME_TRACE_GUID],
                'span_guid': carrier[_TRACER_STATE_PREFIX + _FIELD_NAME_SPAN_GUID],
                'baggage': decoded_baggage,
            })
            return Span(operation_name, self, parent=duck_parent)
        elif format == opentracing.Format.BINARY:
            # TODO: create a basictracer-python impl that uses the .proto
            # encoding from basictracer-go.
            raise NotImplementedError()
        else:
            raise NotImplementedError()

    def _report_span(self, span):
        self.reporter.report_span(span)

    def flush(self):
        return self.reporter.flush()
