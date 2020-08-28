import socket
import sys
import time

import lightstep.constants
import lightstep.recorder
import lightstep.tracer
from basictracer.span import BasicSpan
from basictracer.context import SpanContext
from opentracing.logs import ERROR_KIND, STACK, ERROR_OBJECT
import pytest

from lightstep.crouton import ttypes


class MockConnection(object):
    """MockConnection is used to debug and test Runtime.
    """

    def __init__(self):
        self.reports = []
        self.ready = False

    def open(self):
        self.ready = True

    def report(self, _, report):
        """Mimic the Thrift client's report method. Instead of sending report
            requests save them to a list.
        """
        self.reports.append(report)
        return ttypes.ReportResponse()

    def close(self):
        pass

    def clear(self):
        """Delete the current report requests.
        """
        self.reports[:] = []


@pytest.fixture(params=[True, False])
def recorder(request):
    runtime_args = {
        "collector_encryption": "none",
        "collector_host": "localhost",
        "collector_port": 9998,
        "access_token": "{your_access_token}",
        "component_name": "python/runtime_test",
        "periodic_flush_seconds": 0,
        "use_thrift": request.param,
        "use_http": not request.param,
    }
    yield lightstep.recorder.Recorder(**runtime_args)


def test_default_tags_set_correctly(recorder):
    mock_connection = MockConnection()
    mock_connection.open()
    tags = getattr(recorder._runtime, "tags", None)
    if tags is None:
        tags = getattr(recorder._runtime, "attrs")
    for tag in tags:
        if hasattr(tag, "key"):
            if tag.key == "lightstep.hostname":
                assert tag.string_value == socket.gethostname()
            elif tag.key == "lightstep.tracer_platform":
                assert tag.string_value == "python"
        else:
            if tag.Key == "lightstep.hostname":
                assert tag.Value == socket.gethostname()
            elif tag.Key == "lightstep.tracer_platform":
                assert tag.Value == "python"
    assert len(tags) == 6
    runtime_args = {
        "collector_encryption": "none",
        "collector_host": "localhost",
        "collector_port": 9998,
        "access_token": "{your_access_token}",
        "component_name": "python/runtime_test",
        "periodic_flush_seconds": 0,
        "tags": {"lightstep.hostname": "hostname",},
    }
    new_recorder = lightstep.recorder.Recorder(**runtime_args)
    for tag in new_recorder._runtime.tags:
        if tag.key == "lightstep.hostname":
            assert tag.string_value == "hostname"
    assert len(new_recorder._runtime.tags) == 6


# --------------
# SHUTDOWN TESTS
# --------------
def test_send_spans_after_shutdown(recorder):
    mock_connection = MockConnection()
    mock_connection.open()
    # Send 10 spans
    for i in range(10):
        dummy_basic_span(recorder, i)
    assert recorder.flush(mock_connection)

    # Check 10 spans
    check_spans(recorder.converter, mock_connection.reports[0])

    # Delete current logs and shutdown runtime
    mock_connection.clear()
    recorder.shutdown()

    # Send 10 spans, though none should get through
    for i in range(10):
        recorder.record_span(dummy_basic_span(recorder, i))
    assert not recorder.flush(mock_connection)
    assert len(mock_connection.reports) == 0


def test_shutdown_twice(recorder):
    try:
        recorder.shutdown()
        recorder.shutdown()
    except Exception as error:
        self.fail("Unexpected exception raised: {}".format(error))


# ------------
# STRESS TESTS
# ------------
def test_stress_logs(recorder):
    mock_connection = MockConnection()
    mock_connection.open()
    for i in range(1000):
        dummy_basic_span(recorder, i)
    assert recorder.flush(mock_connection)
    assert recorder.converter.num_span_records(mock_connection.reports[0]) == 1000
    check_spans(recorder.converter, mock_connection.reports[0])


def test_stress_spans(recorder):
    mock_connection = MockConnection()
    mock_connection.open()
    for i in range(1000):
        dummy_basic_span(recorder, i)
    assert recorder.flush(mock_connection)
    assert recorder.converter.num_span_records(mock_connection.reports[0]) == 1000
    check_spans(recorder.converter, mock_connection.reports[0])


# -------------
# RUNTIME TESTS
# -------------
def test_buffer_limits(recorder):
    mock_connection = MockConnection()
    mock_connection.open()
    recorder._max_span_records = 88

    assert len(recorder._span_records) == 0
    for i in range(0, 100):
        dummy_basic_span(recorder, i)
    assert len(recorder._span_records) == 88
    assert recorder.flush(mock_connection)


def check_spans(converter, report):
    """Checks spans' name.
    """
    spans = converter.get_span_records(report)
    for i, span in enumerate(spans):
        assert converter.get_span_name(span) == str(i)


def dummy_basic_span(recorder, i):
    span = BasicSpan(
        lightstep.tracer._LightstepTracer(False, recorder, None),
        operation_name=str(i),
        context=SpanContext(trace_id=1000 + i, span_id=2000 + i),
        start_time=time.time() - 100,
    )
    span.finish()
    return span


def test_exception_formatting(recorder):
    mock_connection = MockConnection()
    mock_connection.open()

    assert len(recorder._span_records) == 0

    span = BasicSpan(
        lightstep.tracer._LightstepTracer(False, recorder, None),
        operation_name="exception span",
        context=SpanContext(trace_id=1000, span_id=2000),
        start_time=time.time() - 100,
    )
    span.log_kv({ERROR_KIND: AttributeError})
    span.finish()
    assert len(recorder._span_records) == 1
    assert recorder.flush(mock_connection)
    spans = recorder.converter.get_span_records(mock_connection.reports[0])
    if hasattr(spans[0], "log_records"):
        assert len(spans[0].log_records) == 1
        assert len(spans[0].log_records[0].fields) == 1
        assert spans[0].log_records[0].fields[0] == ttypes.KeyValue(
            Key="error.kind", Value="AttributeError"
        )
    else:
        assert len(spans[0].logs) == 1
        assert len(spans[0].logs[0].fields) == 1
        assert spans[0].logs[0].fields[0].key == "error.kind"
        assert spans[0].logs[0].fields[0].string_value == "AttributeError"

    span = BasicSpan(
        lightstep.tracer._LightstepTracer(False, recorder, None),
        operation_name="exception span",
        context=SpanContext(trace_id=1000, span_id=2000),
        start_time=time.time() - 100,
    )

    try:
        raise Exception
    except Exception:  # pylint: disable=broad-except
        exc_type, exc_value, exc_tb = sys.exc_info()
        span.log_kv({STACK: exc_tb, ERROR_KIND: exc_type, ERROR_OBJECT: exc_value})

    span.finish()
    assert len(recorder._span_records) == 1
    assert recorder.flush(mock_connection)
    spans = recorder.converter.get_span_records(mock_connection.reports[1])
    if hasattr(spans[0], "log_records"):
        assert len(spans[0].log_records) == 1
        assert len(spans[0].log_records[0].fields) == 3
        assert spans[0].log_records[0].fields[0].Key == "stack"
        assert spans[0].log_records[0].fields[1] == ttypes.KeyValue(
            Key="error.kind", Value="Exception"
        )
        assert spans[0].log_records[0].fields[2] == ttypes.KeyValue(
            Key="error.object", Value=""
        )
    else:
        assert len(spans[0].logs) == 1
        assert len(spans[0].logs[0].fields) == 3
        assert spans[0].logs[0].fields[0].key == "stack"
        assert spans[0].logs[0].fields[1].key == "error.kind"
        assert spans[0].logs[0].fields[1].string_value == "Exception"
        assert spans[0].logs[0].fields[2].key == "error.object"
        assert spans[0].logs[0].fields[2].string_value == ""

