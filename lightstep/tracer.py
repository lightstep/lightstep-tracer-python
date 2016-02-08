"""
LightStep's implementation of the python OpenTracing API.

http://opentracing.io
https://github.com/opentracing/api-python

See the API definition for comments.
"""

import copy
import threading
import traceback
import warnings

import jsonpickle
import opentracing
import opentracing.standard.context

from .crouton import ttypes
from . import constants, reporter as reporter_module, util


FIELD_NAME_TRACE_GUID = 'trace_guid'
FIELD_NAME_SPAN_GUID = 'span_guid'
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
    """
    return Tracer(reporter_module.LightStepReporter(*args, **kwargs))


def init_debug_tracer():
    """Returns a tracer that logs to the console instead of reporting to LightStep.
    """
    return Tracer(reporter_module.LoggingReporter())


class TraceContext(opentracing.standard.context.TraceContext):
    def __init__(self, trace_guid, span_guid, trace_attributes=None):
        super(TraceContext, self).__init__(trace_attributes=trace_attributes)
        self.trace_guid = str(trace_guid)
        self.span_guid = str(span_guid)


class TraceContextSource(object):
    def new_root_trace_context(self):
        trace_guid = util._generate_guid()
        span_guid = util._generate_guid()
        return TraceContext(trace_guid=trace_guid, span_guid=span_guid)

    def new_child_trace_context(self, parent_trace_context):
        try:
            with parent_trace_context.lock:
                trace_attributes = copy.deepcopy(parent_trace_context.trace_attributes)
                ctx = TraceContext(trace_guid=parent_trace_context.trace_guid,
                                   span_guid=util._generate_guid(),
                                   trace_attributes=trace_attributes)
            return ctx, {'parent_span_guid': parent_trace_context.span_guid}
        except Exception as e:
            message = ('Error occured in new_child_trace_context(). Perhaps we did not '
                       'receive a valid parent_trace_context, in which case you should call '
                       'new_root_trace_context() instead of new_child_trace_context() '
                       'or start_trace() instead of join_trace(). Error: {}').format(str(e))
            warnings.warn(message, UserWarning, 3)
            return self.new_root_trace_context(), {}

    def close(self):
        pass


# TODO(misha): Find a binary encoding that works in both python and go
# and then add the corresponding encoding and decoding methods.

class TraceContextEncoder(object):
    def trace_context_to_text(self, trace_context):
        return {FIELD_NAME_TRACE_GUID: str(trace_context.trace_guid),
                FIELD_NAME_SPAN_GUID: str(trace_context.span_guid)}, trace_context.trace_attributes


class TraceContextDecoder(object):
    def trace_context_from_text(self, trace_context_id, trace_attributes):
        trace_guid = int(trace_context_id[FIELD_NAME_TRACE_GUID])
        span_guid = int(trace_context_id[FIELD_NAME_SPAN_GUID])
        # TODO(misha): Think about whether we should validate trace_attributes
        return TraceContext(trace_guid=trace_guid, span_guid=span_guid, trace_attributes=trace_attributes)


class Span(object):
    def __init__(self, operation_name, trace_context, tracer, tags=None):
        self.trace_context = trace_context
        self.tracer = tracer
        self.update_lock = threading.Lock()
        self.logs = []
        self.span_record = ttypes.SpanRecord(
            span_guid=trace_context.span_guid,
            runtime_guid=tracer._runtime_guid,
            span_name=operation_name,
            join_ids=[],
            oldest_micros=util._now_micros(),
            attributes=[],
        )
        self._set_join_id('trace_guid', trace_context.trace_guid)
        if tags:
            for k, v in tags.iteritems():
                self.set_tag(k, v)

    def __enter__(self):
        """Invoked when span is used as a context manager.

        :return: returns the Span itself
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ends context manager and calls finish() on the span.

        If an exception occurrs during execution, it will be logged to the span and re-raised.
        """
        if exc_type:
            # TODO(misha): Consider switching to a public API method once we have one that supports erors and payloads
            self._log_message('Python Exception: ' + exc_type.__name__ + ': ' + str(exc_val),
                              error=True,
                              payload={'exception_type': exc_type.__name__,
                                       'exception_message': str(exc_val),
                                       # TODO(misha) consider using log_record.stack_frames instead
                                       # TODO(misha) consider using just the last n lines of the trace
                                       'exception_trace': traceback.format_exception(exc_type, exc_val, exc_tb)})
        self.finish()
        return False  # A True would suppress the exeception

    def start_child(self, operation_name, tags=None):
        return self.tracer.join_trace(operation_name, self.trace_context, tags)

    def finish(self):
        with self.update_lock:
            self.span_record.youngest_micros = util._now_micros()
        self.tracer.report_span(self)

    def set_tag(self, key, value):
        # TODO(misha): Add support for int and bool tag values.
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

    def info(self, message, *args):
        # We ignore *args for now, because payloads are still in flux.
        return self._log_message(message, error=False)

    def error(self, message, *args):
        # We ignore *args for now, because payloads are still in flux.
        return self._log_message(message, error=True)

    def _log_event(self, event, payload=None):
        """ This is the latest proposal for the api, but it hasn't been released yet, so we'll just use it quietly.
        """
        self._log_message(event, error=False, payload=payload)

    def _log_message(self, message, error, payload=None):
        log_record = ttypes.LogRecord(
            timestamp_micros=util._now_micros(),
            runtime_guid=self.span_record.runtime_guid,
            span_guid=self.span_record.span_guid,
            message=message,
            level=constants.ERROR_LOG if error else constants.INFO_LOG,
            error_flag=error,
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
    def __init__(self, reporter, join_tag_prefix='jointag_'):
        self.trace_context_source = TraceContextSource()
        self.encoder = TraceContextEncoder()
        self.decoder = TraceContextDecoder()
        self.reporter = reporter
        self._runtime_guid = reporter._runtime_guid
        self.join_tag_prefix = join_tag_prefix.lower()

    def start_trace(self, operation_name, tags=None):
        trace_context = self.trace_context_source.new_root_trace_context()
        return Span(operation_name,
                    trace_context,
                    self,
                    tags=tags)

    def join_trace(self, operation_name, parent_trace_context, tags=None):
        trace_context, span_tags = \
            self.trace_context_source.new_child_trace_context(parent_trace_context)
        span = Span(operation_name,
                    trace_context,
                    self,
                    tags=util._merge_dicts(tags, span_tags))
        return span

    def report_span(self, span):
        self.reporter.report_span(span)

    def close(self):
        self.trace_context_source.close()
        return self.reporter.close()

    # TraceContextSource methods
    def new_root_trace_context(self):
        return self.trace_context_source.new_root_trace_context()

    def new_child_trace_context(self, parent_trace_context):
        return self.trace_context_source.new_child_trace_context(parent_trace_context)

    #TraceContextEncoder methods
    def trace_context_to_text(self, trace_context):
        return self.encoder.trace_context_to_text(trace_context)

    #TraceContextDecoder methods
    def trace_context_from_text(self, trace_context_id, trace_attributes):
        return self.decoder.trace_context_from_text(trace_context_id, trace_attributes)
