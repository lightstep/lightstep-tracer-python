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


def test_non_sampled_span_thrift(recorder):

    mock_connection = MockConnection()
    mock_connection.open()

    non_sampled_span = BasicSpan(
        lightstep.tracer._LightstepTracer(False, recorder, None),
        operation_name="non_sampled",
        context=SpanContext(trace_id=1, span_id=1, sampled=False),
        start_time=time.time(),
    )
    non_sampled_span.finish()

    sampled_span = BasicSpan(
        lightstep.tracer._LightstepTracer(False, recorder, None),
        operation_name="sampled",
        context=SpanContext(trace_id=1, span_id=2, sampled=True),
        start_time=time.time(),
    )
    sampled_span.finish()
    recorder.record_span(non_sampled_span)
    recorder.record_span(sampled_span)

    recorder.flush(mock_connection)

    if recorder.use_thrift:
        for span_record in mock_connection.reports[0].span_records:
            assert span_record.span_name == "sampled"
    else:
        for span in mock_connection.reports[0].spans:
            assert span.operation_name == "sampled"


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
        "tags": {"lightstep.hostname": "hostname"},
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
        pytest.fail("Unexpected exception raised: {}".format(error))


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
        for field in spans[0].log_records[0].fields:
            if field.Key == "stack":
                assert "Traceback (most recent call last):" in field.Value
            elif field.Key == "error.kind":
                assert field.Value == "Exception"
            elif field.Key == "error.object":
                assert field.Value == ""
            else:
                raise AttributeError("unexpected field: %s".format(field.Key))
    else:
        assert len(spans[0].logs) == 1
        assert len(spans[0].logs[0].fields) == 3

        for field in spans[0].logs[0].fields:
            if field.key == "stack":
                assert "Traceback (most recent call last):" in field.string_value
            elif field.key == "error.kind":
                assert field.string_value == "Exception"
            elif field.key == "error.object":
                assert field.string_value == ""
            else:
                raise AttributeError("unexpected field: %s".format(field.key))
