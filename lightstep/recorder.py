from abc import ABCMeta, abstractmethod

class SpanRecorder(object):
    """ SpanRecorder's job is record and report a BasicSpan.
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def record_span(self, span):
        pass

class Sampler(object):
    """ Sampler determines the sampling status of a span given its trace ID.

    Expected to return a boolean.
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def sampled(self, trace_id):
        pass

class DefaultSampler(Sampler):
    """ DefaultSampler determines the sampling status via ID % rate == 0
    """
    def __init__(self, rate):
        self.rate = rate

    def sampled(self, trace_id):
        return trace_id % self.rate == 0

########################

class ImplementedSpanRecorder(SpanRecorder):

    def __init__(self, span):
        self.span = span

    def record_span(self):
        print "************THIS IS A TEST: ", self.span
        