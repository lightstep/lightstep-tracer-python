import json
import sys
import base64

import lightstep.tracer
from lightstep.propagation import LightStepFormat
from opentracing import Format


def main():
    tracer = lightstep.Tracer(periodic_flush_seconds=0, collector_host='localhost')
    body = json.load(sys.stdin)

    text_context = extract_http_headers(body, tracer)
    text_carrier = {}
    tracer.inject(text_context, Format.TEXT_MAP, text_carrier)

    binary_context = extract_binary(body, tracer)
    binary_carrier = bytearray()
    tracer.inject(binary_context, LightStepFormat.LIGHTSTEP_BINARY, binary_carrier)
    json.dump({"text_map": text_carrier, "binary": base64.b64encode(binary_carrier)}, sys.stdout)



def extract_http_headers(body, tracer):
    span_context = tracer.extract(Format.TEXT_MAP, body['text_map'])
    return span_context

def extract_binary(body, tracer):
    bin64 = bytearray(base64.b64decode(body['binary']))
    span_context = tracer.extract(LightStepFormat.LIGHTSTEP_BINARY, bin64)
    return span_context

if __name__ == "__main__":
    # execute only if run as a script
    main()
