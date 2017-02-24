"""
LightStep specific carrier formats.
"""

from __future__ import absolute_import


class LightStepFormat(object):
    """A namespace for lightstep supported carrier formats.

    These static constants are intended for use in the Tracer.inject() and
    Tracer.extract() methods. E.g.,

        tracer.inject(span.context, Format.ENVOY_HEADERS, envoy_carrier)

    """

    # The ENVOY_HEADERS format represents SpanContexts in byte array format.
    # https://github.com/opentracing/basictracer-go/blob/master/wire/wire.proto
    ENVOY_HEADERS = 'envoy'
