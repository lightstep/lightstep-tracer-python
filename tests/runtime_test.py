import json
import unittest
import warnings

import jsonpickle

import lightstep.constants
import lightstep.recorder
import lightstep.tracer
import lightstep.instrument
from lightstep.crouton import ttypes

class MockConnection(object):
    """ MockConnection is used to debug and test Runtime.
    """
    def __init__(self):
        self.reports = []
        self.ready = False

    def open(self):
        self.ready = True

    def report(self, _, report):
        """ Mimic the Thrift client's report method. Instead of sending report
            requests save them to a list.
        """
        self.reports.append(report)
        return ttypes.ReportResponse()

    def close(self):
        pass

    def clear(self):
        """ Delete the current report requests.
        """
        self.reports[:] = []

class NewStyleDummyObject(object):
    """ Utilized to test JSON serialization.
    """
    def __init__(self):
        self.obj_payload = None
        self.char_payload = 'a'
        self.bool_payload = True
        self.int_payload = -324234234
        self.double_payload = 3.13123
        self.string_payload = 'Payload String Test'
        self.list_payload = ['item1', 'item2']

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

class OldStyleDummyObject():
    """ Utilized to test JSON serialization.
    """
    def __init__(self):
        self.obj_payload = None
        self.char_payload = 'a'
        self.bool_payload = True
        self.int_payload = -324234234
        self.double_payload = 3.13123
        self.string_payload = 'Payload String Test'
        self.list_payload = ['item1', 'item2']

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

class StressTestObject(NewStyleDummyObject):
    """ Utilized to test JSON serialization with an object that
        contains a large data structure, i.e. a map.
    """
    def __init__(self, num_keys):
        self.array_payload = ['item1', 'item2']
        self.map_payload = {}
        for i in range(num_keys):
            self.map_payload[str(i)] = i

class CyclicObject1(object):
    """ Used to test JSON serialization with cyclic pointers.
    """
    def __init__(self):
        self.message = 'CyclicObject1'
        self.obj_payload = CyclicObject2(self)

class CyclicObject2(object):
    """ Used to test JSON serialization with cyclic pointers.
    """
    def __init__(self, obj_payload):
        self.message = 'CyclicObject2'
        self.obj_payload = obj_payload



class RuntimeTest(unittest.TestCase):
    """ Unit Tests
    """
    def setUp(self):
        self.mock_connection = MockConnection()
        self.mock_connection.open()
        self.mock_reporter = lightstep.reporter.MockReporter()
        self.runtime_args = {'secure': False,
                             'service_host': 'localhost',
                             'service_port': 9998,
                             'access_token': '{your_access_token}',
                             'group_name': 'python/runtime_test',
                             'periodic_flush_seconds': 0}

    def create_test_runtime(self):
        """ Returns a runtime based on self.runtime_args.
        """
        return lightstep.instrument.Runtime(**self.runtime_args)

    def create_test_tracer(self):
        """ Returns a tracer that stores everything in self.mock_reporter.
        """
        return lightstep.tracer.Tracer(self.mock_reporter)

    def create_lightstep_tracer(self):
        return lightstep.tracer.Tracer(
            lightstep.tracer.reporter_module.LightStepReporter(**self.runtime_args))

    # ---------------
    # NO PARAM TESTS
    # ---------------
    def test_init_without_params(self):
        # Won't be able to send logs and spans - but shouldn't crash
        runtime = lightstep.instrument.Runtime()
        runtime._add_log(ttypes.LogRecord(stable_name="Nowhere to go"))
        runtime._add_span(ttypes.SpanRecord(span_name="Nowhere to go span"))
        self.assertFalse(runtime.flush(),
                         "Flush should have failed to reach backend")
        self.assertFalse(runtime.shutdown(flush=True),
                         "Shutdown's flush should have failed to reach backend.")

    # -------------
    # SHUTDOWN TESTS
    # -------------
    def test_send_logs_after_shutdown(self):
        runtime = self.create_test_runtime()

        # Send 10 logs
        for i in range(10):
            runtime._add_log(ttypes.LogRecord(stable_name=str(i)))
        self.assertTrue(runtime.flush(self.mock_connection))

        # Check 10 logs
        self.check_logs(self.mock_connection.reports[0].log_records)

        # Delete current logs and shutdown runtime
        self.mock_connection.clear()
        runtime.shutdown()

        # Send 10 logs, though none should get through
        for i in range(10):
            runtime._add_log(ttypes.LogRecord(stable_name=str(i)))
        self.assertFalse(runtime.flush(self.mock_connection))
        self.assertEqual(len(self.mock_connection.reports), 0)

    def test_shutdown_twice(self):
        runtime = self.create_test_runtime()
        runtime.shutdown()
        runtime.shutdown()

    # ------------------
    # NONE & EMPTY TESTS
    # ------------------
    def test_log_no_log_statement(self):
        runtime = self.create_test_runtime()
        runtime._add_log(ttypes.LogRecord(stable_name=''))
        self.assertTrue(runtime.flush(self.mock_connection))
        self.assertEqual(len(self.mock_connection.reports), 1)
        self.assertEqual(len(self.mock_connection.reports[0].log_records), 1)

    def test_span_no_span_name(self):
        runtime = self.create_test_runtime()
        runtime._add_span(ttypes.SpanRecord(span_name=''))
        self.assertTrue(runtime.flush(self.mock_connection))
        self.assertEqual(len(self.mock_connection.reports[0].span_records), 1)

    # ------------
    # STRESS TESTS
    # ------------
    def test_stress_logs(self):
        runtime = self.create_test_runtime()
        for i in range(1000):
            runtime._add_log(ttypes.LogRecord(stable_name=str(i)))
        self.assertTrue(runtime.flush(self.mock_connection))
        self.assertEqual(len(self.mock_connection.reports[0].log_records), 1000)
        self.check_logs(self.mock_connection.reports[0].log_records)

    def test_stress_spans(self):
        runtime = self.create_test_runtime()
        for i in range(1000):
            runtime._add_span(ttypes.SpanRecord(span_name=str(i)))
        self.assertTrue(runtime.flush(self.mock_connection))
        self.assertEqual(len(self.mock_connection.reports[0].span_records), 1000)
        self.check_spans(self.mock_connection.reports[0].span_records)

    # --------------------------
    # THRIFT VALUE SERIALIZATION
    # --------------------------
    def test_tag_types(self):
        tracer = self.create_lightstep_tracer()
        span = tracer.start_span('test_span')

        # Valid
        span.set_tag('string_key', 'string_value')
        # Coerced to strings
        span.set_tag('string_key', 123)
        span.set_tag('string_key', 123.4)
        span.set_tag('string_key', True)
        # Ignored, but should not interrupt control flow
        span.set_tag('string_key', {'A': '1', 'B': 2 })
        span.set_tag('string_key', set([1, 2, 2]))
        span.finish()

        # TODO: this test attempts, intentionally, to report externally rather
        # than to a mock connection. This is the 'easiest' way to exercise the
        # Thrift serialization code that bawks at the wrong-typed data. The
        # todo herein is to find a more elegant / unit-test-like way to exercise
        # that code.
        #
        # The test here is that this call does not case Thrift to complain.
        tracer.reporter.runtime.flush()

    # -------------
    # PAYLOAD TESTS
    # -------------
    def test_null_payload(self):
        tracer = self.create_test_tracer()
        with tracer.start_span(operation_name='payload span') as span:
            span.log_event('payload log')

        self.assertEqual(self.mock_reporter.spans[0].logs[0].payload_json, None)

    def test_char_payload(self):
        self.log_payload('a')
        self.check_payload('"a"')

    def test_bool_payload(self):
        self.log_payload(True)
        self.check_payload('true')

    def test_int_payload(self):
        self.log_payload(-324234234)
        self.check_payload('-324234234')

    def test_double_payload(self):
        self.log_payload(3.13123)
        self.check_payload('3.13123')

    def test_string_payload(self):
        self.log_payload('Payload String Test')
        self.check_payload('"Payload String Test"')

    def test_list_payload(self):
        self.log_payload(['item1', 'item2'])
        self.check_payload('["item1", "item2"]')

    def _check_span_payload(self, payload, expected):
        self.mock_reporter.clear()
        self.log_payload(payload)
        self.check_payload(expected)

    def test_dict_payload(self):
        d = dict(one=1, two=2, three=3)
        self._check_span_payload({'A': '1', 'B': 2,}, '{"A": "1", "B": 2}')
        self._check_span_payload(dict(one=1, two=2, three=3), '{"one": 1, "two":2, "three":3}')
        self._check_span_payload({'A': 123, 'B' :d}, '{"A": 123, "B": {"one": 1, "three": 3, "two": 2}}')
        self._check_span_payload({'A': set([1, 2, 2])}, '{"A":[1,2]}')

    def test_new_style_object_payload(self):
        self.log_payload(NewStyleDummyObject())
        self.check_payload('{"bool_payload": true, "char_payload": "a", '
                           '"double_payload": 3.13123, "int_payload": -324234234, '
                           '"list_payload": ["item1", "item2"], "obj_payload": null, '
                           '"string_payload": "Payload String Test"}')

    def test_old_style_object_payload(self):
        self.log_payload(OldStyleDummyObject())
        self.check_payload('{"bool_payload": true, "char_payload": "a", '
                           '"double_payload": 3.13123, "int_payload": -324234234, '
                           '"list_payload": ["item1", "item2"], "obj_payload": null, '
                           '"string_payload": "Payload String Test"}')

    def test_stress_object_payload(self):
        stress_obj = StressTestObject(1500)
        self.log_payload(stress_obj)
        self.check_payload(jsonpickle.encode(stress_obj, unpicklable=False))

    def test_cyclic_payload(self):
        obj1 = CyclicObject1()
        self.log_payload(obj1)
        self.check_payload('{"message": "CyclicObject1", "obj_payload": '
                           '{"message": "CyclicObject2", "obj_payload": '
                           '"%s"}}' % obj1.__repr__())

    # ---------
    # TRACER TESTS
    # ---------

    # ---------
    # SPAN TESTS
    # ---------
    def test_span_log(self):
        """ An example of how tracer can be tested.

        We leave most tests commented out since the opentracing api is in flux. Tests should be written when it stablizes.
        """
        tracer = self.create_test_tracer()
        span = tracer.start_span(operation_name='Test Span Infof')
        # span.infof('Hi there %s %s', 'John', 'Smith', payload='Info')
        span.log_event('Hi there John Smith')
        span.finish()

        report_span = self.mock_reporter.spans[0]
        span_record = report_span.span_record
        self.assertEqual(span_record.span_name, 'Test Span Infof')
        log = report_span.logs[0]
        self.assertEqual(log.stable_name, 'Hi there John Smith')
        self.assertEqual(log.level, 'I')
        #self.check_payload(log.payload_json, '{"arguments": ["John", "Smith"], "payload": "Info"}')
        self.assertEqual(log.span_guid, span_record.span_guid)

    def test_span_as_context_manager(self):
        """ Tests that, within a span as a context manager, exceptions are logged and re-raised.
        """
        tracer = self.create_test_tracer()
        exception_caught = False

        try:
            with tracer.start_span(operation_name='test_exception_span') as span:
                span.log_event('Before Error')
                raise RuntimeError("Intentional exception")
                span.log_event('After Error')
        except RuntimeError:
            exception_caught = True

        self.assertTrue(exception_caught)
        logs = self.mock_reporter.spans[0].logs
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0].level, lightstep.constants.INFO_LOG)
        self.assertEqual(logs[0].stable_name, 'Before Error')
        self.assertEqual(logs[1].level, lightstep.constants.INFO_LOG, 'No support for error logs yet')
        self.assertNotEqual(logs[1].stable_name, 'After Error',
                            'Log stable_name after error should never have been logged, it should have been interrupted by the error.')

    def test_buffer_limits(self):
        self.runtime_args.update({'max_log_records': 47,
                                  'max_span_records': 88,})
        runtime = self.create_test_runtime()

        self.assertEqual(len(runtime._log_records), 0)
        self.assertEqual(len(runtime._span_records), 0)
        for i in range(0, 10000):
            runtime._add_log(ttypes.LogRecord(stable_name="Hello World %d!" % (i)))
        self.assertEqual(len(runtime._log_records), 47)
        self.assertTrue(runtime.flush(self.mock_connection))

        self.assertEqual(len(runtime._log_records), 0)
        self.assertEqual(len(runtime._span_records), 0)
        for i in range(0, 10000):
            runtime._add_log(ttypes.LogRecord(stable_name="Hello World %d!" % (i)))
        self.assertEqual(len(runtime._log_records), 47)
        self.assertTrue(runtime.flush(self.mock_connection))

        self.assertEqual(len(runtime._log_records), 0)
        self.assertEqual(len(runtime._span_records), 0)
        for i in range(0, 10000):
            runtime._add_span(ttypes.SpanRecord(span_name="hello_world"))
            runtime._add_log(ttypes.LogRecord(stable_name="Hello World %d!" % (i)))
        self.assertEqual(len(runtime._log_records), 47)
        self.assertEqual(len(runtime._span_records), 88)
        self.assertTrue(runtime.flush(self.mock_connection))

    def test_state_ids(self):
        """
        Test that core tracing ids are serialized properly.
        """
        tracer = self.create_test_tracer()
        # Create a parent and child span and finish each (via with).
        with tracer.start_span(operation_name='parent') as parent:
            with tracer.start_span(operation_name='child', parent=parent) as child:
                # Nothing to do; we're just checking id propagation.
                pass

        parent_span_record = self.mock_reporter.spans[1].span_record
        child_span_record = self.mock_reporter.spans[0].span_record
        self.assertEqual(parent_span_record.span_name, 'parent')
        self.assertEqual(child_span_record.span_name, 'child')
        self.assertEqual(child_span_record.trace_guid, parent_span_record.trace_guid)
        parent_guid = None
        for tagrec in child_span_record.attributes:
            if tagrec.Key == "parent_span_guid":
                parent_guid = tagrec.Value
        self.assertEqual(parent_guid, parent_span_record.span_guid)

    # ------
    # HELPER
    # ------
    def check_logs(self, logs):
        """ Checks logs' stable_name.
        """
        for i, log in enumerate(logs):
            self.assertEqual(log.stable_name, str(i))

    def check_payload(self, expected_payload):
        """ Returns whether correct payload is attached to a log.
        """
        # Note: This is the raw payload that will be pickled by the
        # reporter.
        actual_payload = self.mock_reporter.spans[0].logs[0].payload_json

        sorted_exp = jsonpickle.encode(jsonpickle.decode(expected_payload))
        sorted_act = jsonpickle.encode(actual_payload, unpicklable=False, make_refs=False)
        self.assertEqual(sorted_act, sorted_exp)

    def check_spans(self, spans):
        """ Checks spans' name.
        """
        for i, span in enumerate(spans):
            self.assertEqual(span.span_name, str(i))

    def log_payload(self, payload):
        tracer = self.create_test_tracer()
        with tracer.start_span(operation_name='payload span') as span:
            span.log_event('payload log', payload=payload)
        # Return the tracer in case the caller wants to do more with it.
        return tracer

if __name__ == '__main__':
    unittest.main()
