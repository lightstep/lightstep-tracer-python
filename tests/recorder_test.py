import json
import time
import unittest
import warnings

import jsonpickle

import lightstep.constants
import lightstep.recorder
import lightstep.tracer
import lightstep.recorder
from basictracer.span import BasicSpan
from basictracer.context import SpanContext

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


class RecorderTest(unittest.TestCase):
    """Unit Tests
    """
    def setUp(self):
        self.mock_connection = MockConnection()
        self.mock_connection.open()
        self.runtime_args = {'collector_encryption': 'none',
                             'collector_host': 'localhost',
                             'collector_port': 9998,
                             'access_token': '{your_access_token}',
                             'component_name': 'python/runtime_test',
                             'periodic_flush_seconds': 0}

    def create_test_recorder(self):
        """Returns a LightStep Recorder based on self.runtime_args.
        """
        return lightstep.recorder.Recorder(**self.runtime_args)

    # -------------
    # SHUTDOWN TESTS
    # -------------
    def test_send_spans_after_shutdown(self):
        recorder = self.create_test_recorder()

        # Send 10 spans
        for i in range(10):
            recorder.record_span(self.dummy_basic_span(recorder, i))
        self.assertTrue(recorder.flush(self.mock_connection))

        # Check 10 spans
        self.check_spans(self.mock_connection.reports[0].span_records)

        # Delete current logs and shutdown runtime
        self.mock_connection.clear()
        recorder.shutdown()

        # Send 10 spans, though none should get through
        for i in range(10):
            recorder.record_span(self.dummy_basic_span(recorder, i))
        self.assertFalse(recorder.flush(self.mock_connection))
        self.assertEqual(len(self.mock_connection.reports), 0)

    def test_shutdown_twice(self):
        recorder = self.create_test_recorder()
        recorder.shutdown()
        recorder.shutdown()

    # ------------
    # STRESS TESTS
    # ------------
    def test_stress_logs(self):
        recorder = self.create_test_recorder()
        for i in range(1000):
            recorder.record_span(self.dummy_basic_span(recorder, i))
        self.assertTrue(recorder.flush(self.mock_connection))
        self.assertEqual(len(self.mock_connection.reports[0].span_records), 1000)
        self.check_spans(self.mock_connection.reports[0].span_records)

    def test_stress_spans(self):
        recorder = self.create_test_recorder()
        for i in range(1000):
            recorder.record_span(self.dummy_basic_span(recorder, i))
        self.assertTrue(recorder.flush(self.mock_connection))
        self.assertEqual(len(self.mock_connection.reports[0].span_records), 1000)
        self.check_spans(self.mock_connection.reports[0].span_records)

    # -------------
    # RUNTIME TESTS
    # -------------

    def test_buffer_limits(self):
        self.runtime_args.update({
            'max_span_records': 88,
        })
        recorder = self.create_test_recorder()

        self.assertEqual(len(recorder._span_records), 0)
        for i in range(0, 10000):
            recorder.record_span(self.dummy_basic_span(recorder, i))
        self.assertEqual(len(recorder._span_records), 88)
        self.assertTrue(recorder.flush(self.mock_connection))

    # ------
    # HELPER
    # ------
    def check_spans(self, spans):
        """Checks spans' name.
        """
        for i, span in enumerate(spans):
            self.assertEqual(span.span_name, str(i))

    def dummy_basic_span(self, recorder, i):
        return BasicSpan(
            lightstep.tracer._LightstepTracer(False, recorder),
            operation_name=str(i),
            context=SpanContext(
                trace_id=1000+i,
                span_id=2000+i),
            start_time=time.time())


if __name__ == '__main__':
    unittest.main()
