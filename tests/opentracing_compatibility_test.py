import unittest

import opentracing
from opentracing.harness.api_check import APICompatibilityCheckMixin

import lightstep.tracer


class LightStepTracerOpenTracingCompatibility(unittest.TestCase, APICompatibilityCheckMixin):
    """This unittest currently passes, but then the "Flush Thread" drops a stack trace.

    I believe this is a concurrency problem because this is the first time we have multiple instances of Runtime running in a single binary.
    """
    def tracer(self):
        return lightstep.Tracer(periodic_flush_seconds=0)


if __name__ == '__main__':
    unittest.main()
