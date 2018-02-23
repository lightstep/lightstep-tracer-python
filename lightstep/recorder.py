"""
LightStep's implementations of the basictracer Recorder API.

https://github.com/opentracing/basictracer-python

See the API definition for comments.
"""

import atexit
import jsonpickle
import ssl
import sys
import threading
import time
import traceback
import warnings

from basictracer.recorder import SpanRecorder

from .crouton import ttypes
from . import constants
from . import version as tracer_version
from . import util
from . import connection as conn


class Recorder(SpanRecorder):
    """Recorder translates, buffers, and reports basictracer.BasicSpans.

    These reports are sent to a LightStep collector at the provided address.

    For parameter semantics, see Tracer() documentation; Recorder() respects
    component_name, access_token, collector_host, collector_port,
    collector_encryption, tags, max_span_records, periodic_flush_seconds,
    verbosity, and certificate_verification,
    """
    def __init__(self,
                 component_name=None,
                 access_token='',
                 collector_host='collector.lightstep.com',
                 collector_port=443,
                 collector_encryption='tls',
                 tags=None,
                 max_span_records=constants.DEFAULT_MAX_SPAN_RECORDS,
                 periodic_flush_seconds=constants.FLUSH_PERIOD_SECS,
                 verbosity=0,
                 certificate_verification=True):
        self.verbosity = verbosity
        # Fail fast on a bad access token
        if isinstance(access_token, str) == False:
            raise Exception('access_token must be a string')

        if certificate_verification is False:
            warnings.warn('SSL CERTIFICATE VERIFICATION turned off. ALL FUTURE HTTPS calls will be unverified.')
            ssl._create_default_https_context = ssl._create_unverified_context

        if component_name is None:
            component_name = sys.argv[0]

        # Thrift runtime configuration
        self.guid = util._generate_guid()
        timestamp = util._now_micros()

        python_version = '.'.join(map(str, sys.version_info[0:3]))
        if tags is None:
            tags = {}
        tracer_tags = tags.copy()
        tracer_tags.update({
            'lightstep.tracer_platform': 'python',
            'lightstep.tracer_platform_version': python_version,
            'lightstep.tracer_version': tracer_version.LIGHTSTEP_PYTHON_TRACER_VERSION,
            'lightstep.component_name': component_name,
            'lightstep.guid': util._id_to_hex(self.guid),
            })
        # Convert tracer_tags to a list of KeyValue pairs.
        runtime_attrs = [ttypes.KeyValue(k, util._coerce_str(v)) for (k, v) in tracer_tags.items()]

        # Thrift is picky about the types being correct, so we're explicit here
        self._runtime = ttypes.Runtime(
                util._id_to_hex(self.guid),
                timestamp,
                util._coerce_str(component_name),
                runtime_attrs)
        self._finest("Initialized with Tracer runtime: {0}", (self._runtime,))
        secure = collector_encryption != 'none'  # the default is 'tls'
        self._collector_url = util._collector_url_from_hostport(
                secure,
                collector_host,
                collector_port)
        self._auth = ttypes.Auth(access_token)
        self._mutex = threading.Lock()
        self._span_records = []
        self._max_span_records = max_span_records

        self._disabled_runtime = False
        
        atexit.register(self.shutdown)

        self._periodic_flush_seconds = periodic_flush_seconds
        # _flush_connection and _flush_thread are created lazily since some
        # Python environments (e.g., Tornado) fork() initially and mess up the
        # reporting machinery up otherwise.
        self._flush_connection = None
        self._flush_thread = None
        if self._periodic_flush_seconds <= 0:
            warnings.warn(
                'Runtime(periodic_flush_seconds={0}) means we will never flush to lightstep unless explicitly requested.'.format(
                    self._periodic_flush_seconds))

    def _maybe_init_flush_thread(self):
        """Start a periodic flush mechanism for this recorder if:

        1. periodic_flush_seconds > 0, and 
        2. self._flush_thread is None, indicating that we have not yet
           initialized the background flush thread.

        We do these things lazily because things like `tornado` break if the
        background flush thread starts before `fork()` calls happen.
        """
        if (self._periodic_flush_seconds > 0) and (self._flush_thread is None):
            self._flush_connection = conn._Connection(self._collector_url)
            self._flush_connection.open()
            self._flush_thread = threading.Thread(target=self._flush_periodically,
                                                  name=constants.FLUSH_THREAD_NAME)
            self._flush_thread.daemon = True
            self._flush_thread.start()

    def _fine(self, fmt, args):
        if self.verbosity >= 1:
            fmt_args = fmt.format(*args)
            print("[LightStep Tracer]: ", fmt_args)

    def _finest(self, fmt, args):
        if self.verbosity >= 2:
            fmt_args = fmt.format(*args)
            print("[LightStep Tracer]: ", fmt_args)

    def record_span(self, span):
        """Per BasicSpan.record_span, safely add a span to the buffer.

        Will drop a previously-added span if the limit has been reached.
        """
        if self._disabled_runtime:
            return

        # Lazy-init the flush loop (if need be).
        self._maybe_init_flush_thread()

        # Checking the len() here *could* result in a span getting dropped that
        # might have fit if a report started before the append(). This would only
        # happen if the client lib was being saturated anyway (and likely
        # dropping spans). But on the plus side, having the check here avoids
        # doing a span conversion when the span will just be dropped while also
        # keeping the lock scope minimized.
        with self._mutex:
            if len(self._span_records) >= self._max_span_records:
                return

        span_record = ttypes.SpanRecord(
            trace_guid=util._id_to_hex(span.context.trace_id),
            span_guid=util._id_to_hex(span.context.span_id),
            runtime_guid=util._id_to_hex(self.guid),
            span_name=util._coerce_str(span.operation_name),
            join_ids=[],
            oldest_micros=util._time_to_micros(span.start_time),
            youngest_micros=util._time_to_micros(span.start_time + span.duration),
            attributes=[],
            log_records=[]
        )

        if span.parent_id != None:
            span_record.attributes.append(
                ttypes.KeyValue(
                    constants.PARENT_SPAN_GUID,
                    util._id_to_hex(span.parent_id)))
        if span.tags:
            for key in span.tags:
                if key[:len(constants.JOIN_ID_TAG_PREFIX)] == constants.JOIN_ID_TAG_PREFIX:
                    span_record.join_ids.append(ttypes.TraceJoinId(key, util._coerce_str(span.tags[key])))
                else:
                    span_record.attributes.append(ttypes.KeyValue(key, util._coerce_str(span.tags[key])))

        for log in span.logs:
            event = log.key_values.get('event') or ''
            if len(event) > 0:
                # Don't allow for arbitrarily long log messages.
                if sys.getsizeof(event) > constants.MAX_LOG_MEMORY:
                    event = event[:constants.MAX_LOG_LEN]
            payload = log.key_values.get('payload')
            fields = None
            if log.key_values is not None and len(log.key_values) > 0:
                fields = [ttypes.KeyValue(k, util._coerce_str(v)) for (k, v) in log.key_values.items()]

            span_record.log_records.append(ttypes.LogRecord(
                timestamp_micros=util._time_to_micros(log.timestamp),
                fields=fields))

        with self._mutex:
            if len(self._span_records) < self._max_span_records:
                self._span_records.append(span_record)

    def flush(self, connection=None):
        """Immediately send unreported data to the server.

        Calling flush() will ensure that any current unreported data will be
        immediately sent to the host server.

        If connection is not specified, the report will sent to the server
        passed in to __init__.  Note that custom connections are currently used
        for unit testing against a mocked connection.

        Returns whether the data was successfully flushed.
        """
        if self._disabled_runtime:
            return False

        if connection is not None:
            return self._flush_worker(connection)
        else:
            self._maybe_init_flush_thread()
            return self._flush_worker(self._flush_connection)

    def shutdown(self, flush=True):
        """Shutdown the Runtime's connection by (optionally) flushing the
        remaining logs and spans and then disabling the Runtime.

        Note: spans and logs will no longer be reported after shutdown is called.

        Returns whether the data was successfully flushed.
        """
        # Closing connection twice results in an error. Exit early
        # if runtime has already been disabled.
        if self._disabled_runtime:
            return False

        if flush:
            flushed = self.flush()

        if self._flush_connection:
            self._flush_connection.close()

        self._disabled_runtime = True

        return flushed

    def _flush_periodically(self):
        """Periodically send reports to the server.

        Runs in a dedicated daemon thread (self._flush_thread).
        """
        # Open the connection
        while not self._disabled_runtime and not self._flush_connection.ready:
            time.sleep(self._periodic_flush_seconds)
            self._flush_connection.open()

        # Send data until we get disabled
        while not self._disabled_runtime:
            self._flush_worker(self._flush_connection)
            time.sleep(self._periodic_flush_seconds)

    def _flush_worker(self, connection):
        """Use the given connection to transmit the current logs and spans as a
        report request."""
        if connection == None:
            return False

        # If the connection is not ready, try reestablishing it. If that
        # fails just wait until the next flush attempt to try again.
        if not connection.ready:
            connection.open()
        if not connection.ready:
            return False

        report_request = self._construct_report_request()
        try:
            self._finest("Attempting to send report to collector: {0}", (report_request,))
            resp = connection.report(self._auth, report_request)
            self._finest("Received response from collector: {0}", (resp,))

            # The resp may be None on failed reports
            if resp is not None:
                if resp.commands is not None:
                    for command in resp.commands:
                        if command.disable:
                            self.shutdown(flush=False)
            # Return whether we sent any span data
            return len(report_request.span_records) > 0

        except Exception as e:
            self._fine(
                    "Caught exception during report: {0}, stack trace: {1}",
                    (e, traceback.format_exc()))
            self._restore_spans(report_request.span_records)
            return False


    def _construct_report_request(self):
        """Construct a report request."""
        report = None
        with self._mutex:
            report = ttypes.ReportRequest(self._runtime, self._span_records,
                                          None)
            self._span_records = []
        for span in report.span_records:
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

    def _restore_spans(self, span_records):
        """Called after a flush error to move records back into the buffer
        """
        if self._disabled_runtime:
            return

        with self._mutex:
            if len(self._span_records) >= self._max_span_records:
                return
            combined = span_records + self._span_records
            self._span_records = combined[-self._max_span_records:]
