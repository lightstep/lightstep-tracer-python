"""Simple example showing several generations of spans in a trace.
"""
import argparse
import contextlib
import sys
import time

import opentracing

import lightstep.tracer

def sleep_dot():
    """Short sleep and writes a dot to the STDOUT.
    """
    time.sleep(0.05)
    sys.stdout.write('.')
    sys.stdout.flush()

def add_spans():
    """Calls the opentracing API, doesn't use any LightStep-specific code.
    """
    with opentracing.tracer.start_trace(operation_name='trivial/initial_request') as parent_span:
        parent_span.set_tag('url', 'localhost')
        sleep_dot()
        parent_span.info('All good here! N=%d, flt=%f, string=%s', 42, 3.14, 'xyz')
        parent_span.set_tag('span_type', 'parent')
        sleep_dot()

        # This is how you would represent starting work locally.
        with parent_span.start_child(operation_name='trivial/child_request') as child_span:
            child_span.error('Uh Oh! N=%d, flt=%f, string=%s', 42, 3.14, 'xyz')
            child_span.set_tag('span_type', 'child')
            sleep_dot()

            # To connect remote calls, pass a trace context down the wire.
            trace_context = child_span.trace_context
            with opentracing.tracer.join_trace(operation_name='trivial/remote_span',
                                               parent_trace_context=trace_context) as remote_span:
                remote_span.info('Remote! N=%d, flt=%f, string=%s', 42, 3.14, 'xyz')
                remote_span.set_tag('span_type', 'remote')
                sleep_dot()



def lightstep_tracer_from_args():
    """Initializes lightstep from the commandline args.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--token', help='Your LightStep access token.')
    parser.add_argument('--host', help='The LightStep reporting service host to contact.',
                        default='localhost')
    parser.add_argument('--port', help='The LightStep reporting service port.',
                        type=int, default=9997)
    parser.add_argument('--use_tls', help='Whether to use TLS for reporting',
                        type=bool, default=False)
    parser.add_argument('--group-name', help='The LightStep runtime group',
                        default='Python-Opentracing-Remote')
    args = parser.parse_args()

    if args.use_tls:
	return lightstep.tracer.init_tracer(
	    group_name=args.group_name,
	    access_token=args.token,
	    service_host=args.host,
	    service_port=args.port)
    else:
	return lightstep.tracer.init_tracer(
	    group_name=args.group_name,
	    access_token=args.token,
	    service_host=args.host,
	    service_port=args.port,
	    secure=False)


if __name__ == '__main__':
    print 'Hello '

    # Use opentracing's default no-op implementation
    with contextlib.closing(opentracing.Tracer()) as impl:
        opentracing.tracer = impl
        add_spans()

    #Use LightStep's debug tracer, which logs to the console instead of reporting to LightStep.
    with contextlib.closing(lightstep.tracer.init_debug_tracer()) as impl:
        opentracing.tracer = impl
        add_spans()

    # Use LightStep's opentracing implementation
    with contextlib.closing(lightstep_tracer_from_args()) as impl:
        opentracing.tracer = impl
        add_spans()

    print 'World!'
