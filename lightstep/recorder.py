"""
LightStep's implementations of the basictracer Recorder API.

https://github.com/opentracing/basictracer-python

See the API definition for comments.
"""

from socket import error as socket_error

import atexit
import contextlib
import jsonpickle
import logging
import pprint
import ssl
import sys
import threading
import time
import warnings

from thrift import Thrift
from basictracer.recorder import SpanRecorder

from .crouton import ttypes
from . import constants, version as cruntime_version, util, connection as conn


class Recorder(SpanRecorder):
    """Recorder records and reports a BasicSpan to LightStep."""
    def __init__(self, **kwargs):
        self.runtime = Runtime(**kwargs)

    def record_span(self, span):
        """Per BasicSpan.record_span"""
        self.runtime._add_span(span)

    def flush(self):
        """Force a flush of buffered Span data to LightStep"""
        self.runtime.flush()


class LoggingRecorder(SpanRecorder):
    """LoggingRecorder prints all spans to stdout."""

    def __init__(self, *args, **kwargs):
        self._runtime_guid = util._generate_guid()

    def record_span(self, span):
        """Per BasicSpan.record_span"""

        logs = []
        for log in span.logs:
            event = ""
            if len(log.event) > 0:
                # Don't allow for arbitrarily long log messages.
                if sys.getsizeof(log.event) > constants.MAX_LOG_MEMORY:
                    event = log.event[:constants.MAX_LOG_LEN]
                else:
                    event = log.event
            logs.append(ttypes.LogRecord(
                timestamp_micros=long(util._time_to_micros(log.timestamp)),
                stable_name=event,
                payload_json=log.payload))
        logging.info(
            'Reporting span %s \n with logs %s',
            self._pretty_span(span),
            self._pretty_logs(logs))

    def flush(self):
        """A noop for LoggingRecorder"""
        return

    def _pretty_span(self, span):
        """A helper to format a span for console logging"""
        span = {
            'trace_guid': span.context.trace_id,
            'span_guid': span.context.span_id,
            'runtime_guid': util._id_to_hex(self._runtime_guid),
            'span_name': span.operation_name,
            'oldest_micros': span.start_time,
            'youngest_micros': util._now_micros(),
        }
        return ''.join(['\n ' + attr + ": " + str(span[attr]) for attr in span])

    def _pretty_logs(self, logs):
        """A helper to format logs for console logging"""
        return ''.join(['\n  ' + pprint.pformat(log) for log in logs])


class Runtime(object):
    """Instances of Runtime send spans to the LightStep collector.

    :param str group_name: name identifying the type of service that is being
        tracked
    :param str access_token: project's access token
    :param bool secure: whether HTTP connection is secure
    :param str service_host: Service host name
    :param int service_port: Service port number
    :param int max_span_records: Maximum number of spans records to buffer
    :param bool certificate_verification: if False, will ignore SSL
        certification verification (in ALL HTTPS calls, not just in this
        library) for the lifetime of this process; intended for debugging
        purposes only
    """
    def __init__(self,
                 group_name=None,
                 access_token='',
                 secure=True,
                 service_host="collector.lightstep.com",
                 service_port=443,
                 max_span_records=constants.DEFAULT_MAX_SPAN_RECORDS,
                 certificate_verification=True,
                 periodic_flush_seconds=constants.FLUSH_PERIOD_SECS):

        # Fail fast on a bad access token
        if isinstance(access_token, basestring) == False:
            raise Exception('access_token must be a string')

        if certificate_verification is False:
            warnings.warn('SSL CERTIFICATE VERIFICATION turned off. ALL FUTURE HTTPS calls will be unverified.')
            ssl._create_default_https_context = ssl._create_unverified_context

        if group_name is None:
            group_name = sys.argv[0]

        # Thrift runtime configuration
        self.guid = util._generate_guid()
        timestamp = util._now_micros()

        version = '.'.join(map(str, sys.version_info[0:3]))
        attrs = [
            ttypes.KeyValue("cruntime_platform", "python"),
            ttypes.KeyValue("cruntime_version", cruntime_version.CRUNTIME_VERSION),
            ttypes.KeyValue("python_version", version),
        ]

        # Thrift is picky about the types being correct, so we're explicit here
        self._runtime = ttypes.Runtime(
                util._id_to_hex(self.guid),
                long(timestamp),
                str(group_name),
                attrs)
        self._service_url = util._service_url_from_hostport(secure,
                                                            service_host,
                                                            service_port)
        self._auth = ttypes.Auth(access_token)
        self._mutex = threading.Lock()
        self._span_records = []
        self._max_span_records = max_span_records

        self._disabled_runtime = False
        atexit.register(self.shutdown)

        self._periodic_flush_seconds = periodic_flush_seconds
        if self._periodic_flush_seconds <= 0:
            warnings.warn(
                'Runtime(periodic_flush_seconds={0}) means we will never flush to lightstep unless explicitly requested.'.format(
                    self._periodic_flush_seconds))
            self._flush_connection = None
        else:
            self._flush_connection = conn._Connection(self._service_url)
            self._flush_connection.open()
            self._flush_thread = threading.Thread(target=self._flush_periodically,
                                                  name=constants.FLUSH_THREAD_NAME)
            self._flush_thread.daemon = True
            self._flush_thread.start()

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
        return self._flush_worker(self._flush_connection)


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
            resp = connection.report(self._auth, report_request)

            # The resp may be None on failed reports
            if resp is not None:
                if resp.commands is not None:
                    for command in resp.commands:
                        if command.disable:
                            self.shutdown(flush=False)
            # Return whether we sent any span data
            return len(report_request.span_records) > 0

        except Exception:
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

    def _add_span(self, span):
        """Safely add a span to the buffer.

        Will delete a previously-added span if the limit has been reached.
        """
        if self._disabled_runtime:
            return

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
            runtime_guid=util._id_to_hex(span._tracer.recorder.runtime.guid),
            span_name=str(span.operation_name),
            join_ids=[],
            oldest_micros=long(util._time_to_micros(span.start_time)),
            youngest_micros=long(util._time_to_micros(span.start_time + span.duration)),
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
                    span_record.join_ids.append(ttypes.TraceJoinId(key, span.tags[key]))
                else:
                    span_record.attributes.append(ttypes.KeyValue(key, span.tags[key]))

        for log in span.logs:
            event = ""
            if len(log.event) > 0:
                # Don't allow for arbitrarily long log messages.
                if sys.getsizeof(log.event) > constants.MAX_LOG_MEMORY:
                    event = log.event[:constants.MAX_LOG_LEN]
                else:
                    event = log.event
            span_record.log_records.append(ttypes.LogRecord(
                timestamp_micros=long(util._time_to_micros(log.timestamp)),
                stable_name=event,
                payload_json=log.payload))

        with self._mutex:
            if len(self._span_records) < self._max_span_records:
                self._span_records.append(span_record)

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
