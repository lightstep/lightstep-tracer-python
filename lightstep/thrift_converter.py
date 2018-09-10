from lightstep import constants
from lightstep.converter import Converter
from .crouton import ttypes
import sys
from . import util
from . import version as tracer_version
import jsonpickle


class ThriftConverter(Converter):

    def create_auth(self, access_token):
        return ttypes.Auth(access_token)

    def create_runtime(self, component_name, tags, guid):
        if component_name is None:
            component_name = sys.argv[0]

        python_version = '.'.join(map(str, sys.version_info[0:3]))
        timestamp = util._now_micros()

        if tags is None:
            tags = {}
        tracer_tags = tags.copy()

        tracer_tags.update({
            'lightstep.tracer_platform': 'python',
            'lightstep.tracer_platform_version': python_version,
            'lightstep.tracer_version': tracer_version.LIGHTSTEP_PYTHON_TRACER_VERSION,
            'lightstep.component_name': component_name,
            'lightstep.guid': util._id_to_hex(guid),
        })

        # Convert tracer_tags to a list of KeyValue pairs.
        runtime_attrs = [ttypes.KeyValue(k, util._coerce_str(v)) for (k, v) in tracer_tags.items()]

        # Thrift is picky about the types being correct, so we're explicit here
        return ttypes.Runtime(
            util._id_to_hex(guid),
            timestamp,
            util._coerce_str(component_name),
            runtime_attrs)

    def create_span_record(self, span, guid):
        span_record = ttypes.SpanRecord(
            trace_guid=util._id_to_hex(span.context.trace_id),
            span_guid=util._id_to_hex(span.context.span_id),
            runtime_guid=util._id_to_hex(guid),
            span_name=util._coerce_str(span.operation_name),
            oldest_micros=util._time_to_micros(span.start_time),
            youngest_micros=util._time_to_micros(span.start_time + span.duration),
            attributes=[],
            log_records=[]
        )

        if span.parent_id is not None:
            self.append_attribute(span_record, constants.PARENT_SPAN_GUID, util._id_to_hex(span.parent_id))
        return span_record

    def append_attribute(self, span_record, key, value):
        span_record.attributes.append(ttypes.KeyValue(key, value))

    def append_join_id(self, span_record, key, value):
        span_record.join_ids.append(ttypes.TraceJoinId(key, value))

    def append_log(self, span_record, log):
        fields = None
        if log.key_values is not None and len(log.key_values) > 0:
            fields = [ttypes.KeyValue(k, util._coerce_str(v)) for (k, v) in log.key_values.items()]

        span_record.log_records.append(ttypes.LogRecord(
            timestamp_micros=util._time_to_micros(log.timestamp),
            fields=fields))

    def create_report(self, runtime, span_records):
        report = ttypes.ReportRequest(runtime, span_records, None)
        for span in report.span_records:
            if not span.log_records:
                continue
            for log in span.log_records:
                index = span.log_records.index(log)
                if log.payload_json is not None:
                    try:
                        log.payload_json = \
                            jsonpickle.encode(log.payload_json,
                                              unpicklable=False,
                                              make_refs=False,
                                              max_depth=constants.JSON_MAX_DEPTH)
                    except:
                        log.payload_json = jsonpickle.encode(constants.JSON_FAIL)
                span.log_records[index] = log
        return report

    def combine_span_records(self, report_request, span_records):
        return report_request.span_records + span_records

    def num_span_records(self, report_request):
        return len(report_request.span_records)

    def get_span_records(self, report_request):
        return report_request.span_records

    def get_span_name(self, span_record):
        return span_record.span_name
