from .basictracer.recorder import SpanRecorder
from .crouton import ttypes

import util
import logging
import constants
import pprint
import sys

import atexit
import contextlib
import jsonpickle
import random
from socket import error as socket_error
import ssl
import threading
import time
import warnings

from thrift import Thrift
from . import constants, version as cruntime_version, util, connection as conn #???


class Recorder(SpanRecorder):
    """ SpanRecorder's job is record and report a BasicSpan.
    """
    def __init__(self, *args, **kwargs):
        self.runtime = Runtime(*args, **kwargs)
        self._runtime_guid = self.runtime._runtime.guid

    def record_span(self, span):
        self.runtime._add_span(span)

    def flush(self):
        self.runtime.flush()

def _pretty_logs(logs):
    return ''.join(['\n  ' + pprint.pformat(log) for log in logs])
def _pretty_span(span):
    span = {'trace_guid': span.context.trace_id, 'span_guid':span.context.span_id, 'runtime_guid':span._tracer.recorder._runtime_guid,
     'span_name':span.operation_name, 'oldest_micros':span.start_time, 'youngest_micros':util._now_micros()}
    return ''.join(['\n ' + attr + ": " + str(span[attr]) for attr in span])

class LoggingRecorder(SpanRecorder):

    """Logs all spans to console."""
    def __init__(self, *args, **kwargs):
        self._runtime_guid = util._generate_guid()

    def record_span(self,span):
        logs = []
        for log in span.logs:
            event = ""
            if len(log.event)>0:
                #Don't allow for arbitrarily long log messages.
                if sys.getsizeof(log.event)>constants.MAX_LOG_MEMORY:
                    event = log.event[:constants.MAX_LOG_LEN]
                else:
                    event = log.event
            logs.append(ttypes.LogRecord(stable_name= event, payload_json= log.payload))
        logging.warn('Reporting span %s \n with logs %s', _pretty_span(span), _pretty_logs(logs))

    def flush(self):
        return True

class Runtime(object):
    """Instances of Runtime are used to sends logs and spans to the server.

    :param str group_name: name identifying the type of service that is being
        tracked
    :param str access_token: project's access token
    :param bool secure: whether HTTP connection is secure
    :param str service_host: Service host name
    :param int service_port: Service port number
    :param int max_log_records: Maximum number of log records to buffer
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
                 max_log_records=constants.DEFAULT_MAX_LOG_RECORDS,
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
        guid = util._generate_guid()
        timestamp = util._now_micros()

        version = '.'.join(map(str, sys.version_info[0:3]))
        attrs = [
            ttypes.KeyValue("cruntime_platform", "python"),
            ttypes.KeyValue("cruntime_version", cruntime_version.CRUNTIME_VERSION),
            ttypes.KeyValue("python_version", version),
        ]

        # Thrift is picky about the types being correct, so we're explicit here
        self._runtime = ttypes.Runtime(str(guid), long(timestamp), str(group_name), attrs)
        self._service_url = util._service_url_from_hostport(secure,
                                                            service_host,
                                                            service_port)
        self._auth = ttypes.Auth(access_token)
        self._mutex = threading.Lock()
        self._log_records, self._span_records = ([] for i in range(2))

        self._max_log_records = max_log_records
        self._max_span_records = max_span_records

        if self._max_log_records <= 0:
            raise Exception()

        self._disabled_runtime = False
        atexit.register(self.shutdown)

        self._periodic_flush_seconds = periodic_flush_seconds
        if self._periodic_flush_seconds <= 0:
            warnings.warn(
                'Runtime(periodic_flush_seconds={0}) means we will never flush to lightstep unless explicitly requested.'.format(
                    self._periodic_flush_seconds))
            self._periodic_flush_connection = None
        else:
            self._periodic_flush_connection = conn._Connection(self._service_url)
            self._periodic_flush_connection.open()
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
        self._disabled_runtime = True

        if flush:
            flushed = self._flush_with_new_connection()

        if self._periodic_flush_connection:
            self._periodic_flush_connection.close()

        return flushed

    def flush(self, connection=None):
        """Immediately send unreported data to the server.

        Calling flush() will ensure that any current unreported data will be
        immediately sent to the host server.

        If connection is not specified, the report will sent to the server
        passed in to __init__.

        Returns whether the data was successfully flushed.
        """
        if self._disabled_runtime:
            return False

        if connection is not None:
            return self._flush_worker(connection)

        return self._flush_with_new_connection()

    def _flush_with_new_connection(self):
        """Flush, starting a new connection first."""
        with contextlib.closing(conn._Connection(self._service_url)) as connection:
            connection.open()
            return self._flush_worker(connection)

    def _flush_periodically(self):
        """Periodically send reports to the server.

        Runs in a dedicated daemon thread (self._flush_thread).
        """
        # Open the connection
        while not self._disabled_runtime and not self._periodic_flush_connection.ready:
            time.sleep(self._periodic_flush_seconds)
            self._periodic_flush_connection.open()

        # Send data until we get disabled
        while not self._disabled_runtime:
            self._flush_worker(self._periodic_flush_connection)
            time.sleep(self._periodic_flush_seconds)

    def _flush_worker(self, connection):
        """Use the given connection to transmit the current logs and spans as a
        report request."""
        if not connection.ready:
            return False

        report_request = self._construct_report_request()
        try:
            resp = connection.report(self._auth, report_request)
            if resp.commands is not None:
                for command in resp.commands:
                    if command.disable:
                        self.shutdown(flush=False)
            return True

        except (Thrift.TException, socket_error):
            self._store_on_disconnect(report_request)
            return False

    def _construct_report_request(self):
        """Construct a report request."""
        report = None
        with self._mutex:
            report = ttypes.ReportRequest(self._runtime, self._span_records,
                                          None)
            self._span_records = []
            self._log_records = []
        for span in report.span_records:
            for log in span.log_records:
                if log.payload_json is not None:
                    try:
                        log.payload_json = \
                                           jsonpickle.encode(log.payload_json,
                                                             unpicklable=False,
                                                             make_refs=False,
                                                             max_depth=constants.JSON_MAX_DEPTH)
                    except:
                        log.payload_json = jsonpickle.encode(constants.JSON_FAIL)
        return report

    def _add_log(self, log):
        """Safely add a log to the buffer.

        Will delete a previously-added log if the limit has been reached.
        """
        if self._disabled_runtime:
            return
        with self._mutex:
            current_len = len(self._log_records)
            if current_len >= self._max_log_records:
                delete_index = random.randint(0, current_len - 1)
                self._log_records[delete_index] = log
            else:
                self._log_records.append(log)

    def _add_span(self, span):
        """Safely add a span to the buffer.

        Will delete a previously-added span if the limit has been reached.
        """
        now_micros = util._now_micros()
        
        span_record = ttypes.SpanRecord(
            trace_guid=str(span.context.trace_id),
            span_guid=str(span.context.span_id),
            runtime_guid=str(span._tracer.recorder._runtime_guid),
            span_name=str(span.operation_name),
            join_ids=[],
            oldest_micros=long(span.start_time),
            youngest_micros = long(now_micros),
            attributes=[],
            log_records=[]
        )

        for key in span.tags:
            if key[:len(constants.JOIN_ID_TAG_PREFIX)] == constants.JOIN_ID_TAG_PREFIX:
                span_record.join_ids.append(ttypes.TraceJoinId(key, span.tags[key]))
            else:
                span_record.attributes.append(ttypes.KeyValue(key, span.tags[key]))

        for log in span.logs:
            event = ""
            if len(log.event)>0:
                #Don't allow for arbitrarily long log messages.
                if sys.getsizeof(log.event)>constants.MAX_LOG_MEMORY:
                    event = log.event[:constants.MAX_LOG_LEN]
                else:
                    event = log.event
            span_record.log_records.append(ttypes.LogRecord(stable_name= event, payload_json= log.payload))


        if self._disabled_runtime:
            return
        with self._mutex:
            current_len = len(self._span_records)
            if len(self._span_records) >= self._max_span_records:
                delete_index = random.randint(0, current_len - 1)
                self._span_records[delete_index] = span_record
            else:
                self._span_records.append(span_record)



    def _store_on_disconnect(self, report_request):
        """Store logs and the spans from a report request in the runtime's
        buffers."""
        for log in report_request.log_records:
            self._add_log(log)
        for span in report_request.span_records:
            self._add_span(span)
        

        