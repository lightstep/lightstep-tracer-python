"""
LightStep's implementations of the basictracer Recorder API.

https://github.com/opentracing/basictracer-python

See the API definition for comments.
"""

import atexit
import ssl
import threading
import time
import traceback
import warnings

from basictracer.recorder import SpanRecorder
from opentracing.logs import ERROR_KIND, STACK

from lightstep.http_converter import HttpConverter
from lightstep.thrift_converter import ThriftConverter
from . import constants
from . import util
from lightstep.thrift_connection import _ThriftConnection
from lightstep.http_connection import _HTTPConnection


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
                 certificate_verification=True,
                 use_thrift=False,
                 use_http=True,
                 timeout_seconds=30):
        self.verbosity = verbosity
        # Fail fast on a bad access token
        if not isinstance(access_token, str):
            raise Exception('access_token must be a string')

        if certificate_verification is False:
            warnings.warn('SSL CERTIFICATE VERIFICATION turned off. ALL FUTURE HTTPS calls will be unverified.')
            ssl._create_default_https_context = ssl._create_unverified_context

        if use_http:
            self.use_thrift = False
            self.converter = HttpConverter()
        elif use_thrift:
            self.use_thrift = True
            self.converter = ThriftConverter()
        else:
            raise Exception('Either use_thrift or use_http must be True')

        self.guid = util._generate_guid()
        self._runtime = self.converter.create_runtime(component_name, tags, self.guid)
        self._finest("Initialized with Tracer runtime: {0}", (self._runtime,))
        secure = collector_encryption != 'none'  # the default is 'tls'
        self._collector_url = util._collector_url_from_hostport(
                secure,
                collector_host,
                collector_port,
                self.use_thrift)
        self._timeout_seconds = timeout_seconds
        self._auth = self.converter.create_auth(access_token)
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
            if self.use_thrift:
                self._flush_connection = _ThriftConnection(self._collector_url)
            else:
                self._flush_connection = _HTTPConnection(self._collector_url, self._timeout_seconds)
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

        span_record = self.converter.create_span_record(span, self.guid)

        if span.tags:
            for key in span.tags:
                if key[:len(constants.JOIN_ID_TAG_PREFIX)] == constants.JOIN_ID_TAG_PREFIX:
                    self.converter.append_join_id(span_record, key, util._coerce_str(span.tags[key]))
                else:
                    self.converter.append_attribute(span_record, key, util._coerce_str(span.tags[key]))

        for log in span.logs:
            self.converter.append_log(span_record, self._normalize_log(log))

        with self._mutex:
            if len(self._span_records) < self._max_span_records:
                self._span_records.append(span_record)

    def _normalize_log(self, log):
        if log.key_values is not None and len(log.key_values) > 0:

            if ERROR_KIND in log.key_values:
                log.key_values[ERROR_KIND] = util._format_exc_type(log.key_values[ERROR_KIND])

            if STACK in log.key_values:
                log.key_values[STACK] = util._format_exc_tb(log.key_values[STACK])

        return log

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
            return self.converter.num_span_records(report_request) > 0

        except Exception as e:
            self._fine(
                    "Caught exception during report: {0}, stack trace: {1}",
                    (e, traceback.format_exc()))
            self._restore_spans(report_request)
            return False

    def _construct_report_request(self):
        """Construct a report request."""
        report = None
        with self._mutex:
            report = self.converter.create_report(self._runtime, self._span_records)
            self._span_records = []
        return report

    def _restore_spans(self, report_request):
        """Called after a flush error to move records back into the buffer
        """
        if self._disabled_runtime:
            return

        with self._mutex:
            if len(self._span_records) >= self._max_span_records:
                return
            combined = self.converter.combine_span_records(report_request, self._span_records)
            self._span_records = combined[-self._max_span_records:]
