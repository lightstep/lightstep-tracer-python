from .basictracer.recorder import SpanRecorder
from .crouton import ttypes

import instrument
import util
import logging
import constants
import pprint
import sys


class Recorder(SpanRecorder):
    """ SpanRecorder's job is record and report a BasicSpan.
    """
    def __init__(self, *args, **kwargs):
        self.runtime = instrument.Runtime(*args, **kwargs)
        self._runtime_guid = self.runtime._runtime.guid

    def record_span(self, span):
        now_micros = util._now_micros()
        
        spanRecord = ttypes.SpanRecord(
            trace_guid=str(span.context.trace_id),
            span_guid=str(span.context.span_id),
            runtime_guid=str(span._tracer.recorder._runtime_guid),
            span_name=str(span.operation_name),
            join_ids=[],
            oldest_micros=long(span.start_time),
            youngest_micros = long(now_micros),
            attributes=[],
        )

        for key in span.tags:
            if key[:5] == "join:":
                spanRecord.join_ids.append(ttypes.TraceJoinId(key, span.tags[key]))
            else:
                spanRecord.attributes.append(ttypes.KeyValue(key, span.tags[key]))

        self.runtime._add_span(spanRecord)

        for log in span.logs:
            event = ""
            if len(log.event)>0:
                #Don't allow for arbitrarily long log messages.
                if sys.getsizeof(log.event)>constants.flagMaxLogMessageLen:
                    event = log.event[:constants.maxLenofLogMessage]
                else:
                    event = log.event
            self.runtime._add_log(ttypes.LogRecord(stable_name= event, payload_json= log.payload))

    def flush(self):
        self.runtime.flush()

def _pretty_logs(logs):
    return ''.join(['\n  ' + pprint.pformat(log) for log in logs])

class LoggingRecorder(SpanRecorder):

    """Logs all spans to console."""

    def __init__(self, *args, **kwargs):
        self.runtime = instrument.Runtime(*args, **kwargs)
        self._runtime_guid = self.runtime._runtime.guid

    def record_span(self,span):
        now_micros = util._now_micros()
        span_record = ttypes.SpanRecord(
            trace_guid=str(span.context.trace_id),
            span_guid=str(span.context.span_id),
            runtime_guid=str(span._tracer._runtime_guid),
            span_name=str(span.operation_name),
            join_ids=[],
            oldest_micros=long(span.start_time),
            youngest_micros = long(now_micros),
            attributes=[],
        ) 
        logging.warn('Reporting span %s \n with logs %s', pprint.pformat(vars(span_record)), _pretty_logs(span.logs))

    def flush(self):
        return True
        

        