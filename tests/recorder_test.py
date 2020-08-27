import socket
import time
import unittest

import lightstep.constants
import lightstep.recorder
import lightstep.tracer
import lightstep.recorder
from basictracer.span import BasicSpan
from basictracer.context import SpanContext
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
        "tags": {
            "lightstep.hostname": "hostname",
        },
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
