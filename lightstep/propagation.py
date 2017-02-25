"""
LightStep specific carrier formats.
"""

from __future__ import absolute_import


class LightStepFormat(object):
    """A namespace for lightstep supported carrier formats.

    These static constants are intended for use in the Tracer.inject() and
    Tracer.extract() methods. E.g.,

        tracer.inject(span.context, LightStepFormat.LIGHTSTEP_BINARY, lightstep_carrier)

    """

    # The LIGHTSTEP_BINARY format represents SpanContexts in byte array format.
    # https://github.com/lightstep/lightstep-tracer-common/lightstep_carrier.proto
    LIGHTSTEP_BINARY = 'lightstep_binary'
