class Context(object):
    """ Context holds the trace context for a span.

    trace_id, span_id, and parent_span_id are uint64's, so their range is
    anywhere between 0 to 2^64 - 1
    """

    def __init__(self, trace_id=None, span_id=None, parent_id=None, baggage=None, sampled=True):
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_id = parent_id
        self.sampled = sampled
        self.baggage = baggage
