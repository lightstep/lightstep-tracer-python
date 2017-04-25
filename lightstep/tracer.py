"""
LightStep's implementation of the python OpenTracing API.

http://opentracing.io
https://github.com/opentracing/api-python

See the API definition for comments.
"""
from __future__ import absolute_import

from basictracer import BasicTracer
from basictracer.text_propagator import TextPropagator
from opentracing import Format

from lightstep.lightstep_binary_propagator import LightStepBinaryPropagator
from lightstep.propagation import LightStepFormat
from .recorder import Recorder


def Tracer(**kwargs):
    """Instantiates LightStep's OpenTracing implementation.

    :param str component_name: the human-readable identity of the instrumented
        process. I.e., if one drew a block diagram of the distributed system,
        the component_name would be the name inside the box that includes this
        process.
    :param str access_token: the LightStep project's access token
    :param str collector_host: LightStep collector hostname
    :param int collector_port: LightStep collector port
    :param str collector_encryption: one of 'tls' or 'none'. If nothing is
        specified, the default is 'tls'.
    :param dict tags: a string->string dict of tags for the Tracer itself (as
        opposed to the Spans it records)
    :param int max_span_records: Maximum number of spans records to buffer
    :param int periodic_flush_seconds: seconds between periodic background
        flushes, or 0 to disable background flushes entirely.
    :param int verbosity: verbosity for (debug) logging, all via logging.info().
        0 (default): log nothing
        1: log transient problems
        2: log all of the above, along with payloads sent over the wire
    :param bool certificate_verification: if False, will ignore SSL
        certification verification (in ALL HTTPS calls, not just in this
        library) for the lifetime of this process; intended for debugging
        purposes only. (Included to work around SNI non-conformance issues
        present in some versions of python)
    :param bool disable_binary_format: Whether to disable the binary
        inject/extract format (which relies on protobufs and may cause problems
        if other versions of protobufs are active in the same packaging
        configuration). Defaults to False (i.e., binary format is enabled).
    """
    enable_binary_format = True
    if 'disable_binary_format' in kwargs:
        enable_binary_format = not kwargs['disable_binary_format']
        del kwargs['disable_binary_format']
    return _LightstepTracer(enable_binary_format, Recorder(**kwargs))


class _LightstepTracer(BasicTracer):
    def __init__(self, enable_binary_format, recorder):
        """Initialize the LightStep Tracer, deferring to BasicTracer."""
        super(_LightstepTracer, self).__init__(recorder)
        self.register_propagator(Format.TEXT_MAP, TextPropagator())
        self.register_propagator(Format.HTTP_HEADERS, TextPropagator())
        if enable_binary_format:
            # We do this import lazily because protobuf versioning issues
            # can cause process-level failure at import time.
            from basictracer.binary_propagator import BinaryPropagator
            self.register_propagator(Format.BINARY, BinaryPropagator())
            self.register_propagator(LightStepFormat.LIGHTSTEP_BINARY, LightStepBinaryPropagator())

    def flush(self):
        """Force a flush of buffered Span data to the LightStep collector."""
        self.recorder.flush()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.flush()
