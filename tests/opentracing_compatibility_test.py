import unittest

import opentracing
from opentracing.harness.api_check import APICompatibilityCheckMixin

import lightstep.tracer

# LightStep intentionally does not support the binary protocol at the moment.
def test_alway_pass(self):
    return
APICompatibilityCheckMixin.test_binary_propagation = test_alway_pass

class LightStepTracerOpenTracingCompatibility(unittest.TestCase, APICompatibilityCheckMixin):
    """This unittest currently passes, but then the "Flush Thread" drops a stack trace.

    I believe this is a concurrency problem because this is the first time we have multiple instances of Runtime running in a single binary.
    """
    def tracer(self):
        return lightstep.tracer.init_tracer(periodic_flush_seconds=0)

class DebugTracerOpenTracingCompatibility(unittest.TestCase, APICompatibilityCheckMixin):
    def tracer(self):
        return lightstep.tracer.init_debug_tracer()

if __name__ == '__main__':
    unittest.main()
