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
import warnings

import jsonpickle
import opentracing

from .crouton import ttypes
from . import constants, reporter as reporter_module, util


_TRACER_STATE_PREFIX = "ts-"
_BAGGAGE_PREFIX = "bg-"
_FIELD_NAME_TRACE_GUID = 'traceguid'
_FIELD_NAME_SPAN_GUID = 'spanguid'
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
            self.trace_guid = parent.trace_guid
            self.parent_guid = parent.span_guid
            self.span_guid = util._generate_guid()
            self.baggage = copy.deepcopy(parent.baggage)

        self.update_lock = threading.Lock()
        self.logs = []
        if start_time is None:
            oldest_micros = util._now_micros()
        else:
            oldest_micros = util._time_to_micros(start_time)
        self.span_record = ttypes.SpanRecord(
            span_guid=self.span_guid,
            runtime_guid=tracer._runtime_guid,
            span_name=operation_name,
            join_ids=[],
            oldest_micros=oldest_micros,
            attributes=[],
        )
        self._set_join_id('trace_guid', self.trace_guid)
        if tags:
            for k, v in tags.iteritems():
                self.set_tag(k, v)

    def finish(self):
        with self.update_lock:
            self.span_record.youngest_micros = util._now_micros()
        self.tracer._report_span(self)

    def set_operation_name(self, operation_name):
        with self.update_lock:
            self.span_record.span_name = operation_name
        return self

    def set_tag(self, key, value):
        if not isinstance(key, basestring):
            warnings.warn('set_tag key must be a string. Tag ignored.', UserWarning, 3)
            return self

        if (isinstance(value, int) or
            isinstance(value, long) or
            isinstance(value, float) or
            isinstance(value, bool)):
            # The Thrift binary protocol being used currently requires all the
            # tag values to be strings.
            value = str(value)
        if not isinstance(value, basestring):
            warnings.warn('set_tag value must be coerce-able to a string. Tag ignored.', UserWarning, 3)
            return self

        # TODO(misha): Canonicalize key more thoroughly.
        key = key.lower()
        if key.startswith(self.tracer.join_tag_prefix):
            key = key[len(self.tracer.join_tag_prefix):]
            self._set_join_id(key, value)
        else:
            self._set_attribute(key, value)
        return self

    def _set_join_id(self, key, value):
        with self.update_lock:
            trace_join_id = ttypes.TraceJoinId(key, value)
            self.span_record.join_ids.append(trace_join_id)

    def _set_attribute(self, key, value):
        with self.update_lock:
            attribute = ttypes.KeyValue(key, value)
            self.span_record.attributes.append(attribute)

    def set_baggage_item(self, key, value):
        with self.update_lock:
            self.baggage[key.lower()] = value
        return self

    def get_baggage_item(self, key):
        canon_key = key.lower()
        with self.update_lock:
            if self.baggage.has_key(canon_key):
                return self.baggage[canon_key]
            else:
                return None

    def log_event(self, event, payload=None):
        return self._log_explicit(time.time(), event, payload)

    def log(self, **kwargs):
        timestamp = (kwargs["timestamp"]
                     if kwargs.has_key("timestamp")
                     else time.time())
        event = (kwargs["event"]
                 if kwargs.has_key("event")
                 else "")
        payload = (kwargs["payload"]
                   if kwargs.has_key("payload")
                   else None)

        return self._log_explicit(timestamp, event, payload)

    def _log_explicit(self, timestamp, event, payload=None):
        log_record = ttypes.LogRecord(
            timestamp_micros=util._now_micros(),
            runtime_guid=self.span_record.runtime_guid,
            span_guid=self.span_guid,
            stable_name=event,
            level=constants.INFO_LOG,
            error_flag=False,
        )

        if payload is not None:
            try:
                log_record.payload_json = \
                    jsonpickle.encode(payload,
                                      unpicklable=False,
                                      make_refs=False,
                                      max_depth=constants.JSON_MAX_DEPTH)
            except:
                log_record.payload_json = jsonpickle.encode(constants.JSON_FAIL)

        with self.update_lock:
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
        self._split_text_ie = _SplitTextInjectorExtractor(self)
        self._split_binary_ie = _SplitBinaryInjectorExtractor(self)

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

    def injector(self, format):
        if format == opentracing.Format.SPLIT_TEXT:
            return self._split_text_ie
        elif format == opentracing.Format.SPLIT_BINARY:
            return self._split_binary_ie
        else:
            raise NotImplementedError()

    def extractor(self, format):
        if format == opentracing.Format.SPLIT_TEXT:
            return self._split_text_ie
        elif format == opentracing.Format.SPLIT_BINARY:
            return self._split_binary_ie
        else:
            raise NotImplementedError()

    def _report_span(self, span):
        self.reporter.report_span(span)

    def flush(self):
        return self.reporter.flush()


class _SplitTextInjectorExtractor:
    def __init__(self, tracer):
        self._tracer = tracer

    def inject_span(self, span, carrier):
        carrier.tracer_state = {
            _TRACER_STATE_PREFIX + _FIELD_NAME_TRACE_GUID: span.trace_guid,
            _TRACER_STATE_PREFIX + _FIELD_NAME_SPAN_GUID: span.span_guid,
        }
        carrier.baggage = {}
        for k, v in span.baggage.iteritems():
            carrier.baggage[_BAGGAGE_PREFIX + k] = v

    def join_trace(self, operation_name, carrier):
        decoded_baggage = {}
        for k in carrier.baggage:
            if k.lower().startswith(_BAGGAGE_PREFIX):
                decoded_baggage[k.lower()[len(_BAGGAGE_PREFIX):]] = carrier.baggage[k]
        duck_parent = type('', (), {
            'trace_guid': carrier.tracer_state[_TRACER_STATE_PREFIX + _FIELD_NAME_TRACE_GUID],
            'span_guid': carrier.tracer_state[_TRACER_STATE_PREFIX + _FIELD_NAME_SPAN_GUID],
            'baggage': decoded_baggage,
        })
        return Span(operation_name, self._tracer, parent=duck_parent)


# TODO: settle on an efficient in-band binary format for LightStep.
class _SplitBinaryInjectorExtractor:
    def __init__(self, tracer):
        self._tracer = tracer

    def inject_span(self, span, carrier):
        ts_dict = {
            _FIELD_NAME_TRACE_GUID: span.trace_guid,
            _FIELD_NAME_SPAN_GUID: span.span_guid,
        }
        carrier.tracer_state = bytearray(json.dumps(ts_dict))
        carrier.baggage = bytearray(json.dumps(span.baggage))

    def join_trace(self, operation_name, carrier):
        ts_dict = json.loads(carrier.tracer_state.decode('utf-8'))
        duck_parent = type('', (), {
            'trace_guid': ts_dict[_FIELD_NAME_TRACE_GUID],
            'span_guid': ts_dict[_FIELD_NAME_SPAN_GUID],
            'baggage': json.loads(carrier.baggage.decode('utf-8')),
        })
        return Span(operation_name, self._tracer, parent=duck_parent)
