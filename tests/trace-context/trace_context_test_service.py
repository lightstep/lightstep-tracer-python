from json import dumps
from logging import getLogger, basicConfig, DEBUG

from requests import post
from flask import request, Flask

from opentracing.ext import tags
from opentracing.propagation import Format
from lightstep import Tracer
from lightstep.trace_context import TraceContextPropagator

app = Flask(__name__)


getLogger('').handlers = []
basicConfig(format='%(message)s', level=DEBUG)

tracer = Tracer(periodic_flush_seconds=0, collector_host="localhost")
tracer.register_propagator(Format.HTTP_HEADERS, TraceContextPropagator())


@app.route("/test", methods=["POST"])
def hello():

    span_ctx = tracer.extract(Format.HTTP_HEADERS, request.headers)
    span_tags = {tags.SPAN_KIND: tags.SPAN_KIND_RPC_SERVER}

    for action in request.json:
        with (
            tracer.start_active_span(
                'format', child_of=span_ctx, tags=span_tags
            )
        ) as scope:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
            }

            tracer.inject(scope.span.context, Format.HTTP_HEADERS, headers)

            hello_to = request.args.get('helloTo')

            post(
                url=action["url"],
                data=dumps(action["arguments"]),
                headers=headers,
                timeout=5.0,
            )

    return 'Hello, {}!'.format(hello_to)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
