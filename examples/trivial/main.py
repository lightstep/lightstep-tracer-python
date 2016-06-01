"""Simple example showing several generations of spans in a trace.
"""
import argparse
import contextlib
import sys
import time

import opentracing

import sys
import os
sys.path.append('/Users/hugozul/lightstep-tracer-python')

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
    with opentracing.tracer.start_span(operation_name='trivial/initial_request') as parent_span:
        parent_span.set_tag('url', 'localhost')
        sleep_dot()
        parent_span.log_event('All good here!', payload={'N': 42, 'pi': 3.14, 'abc': 'xyz'})
        parent_span.set_tag('span_type', 'parent')
        parent_span.set_baggage_item('checked', 'baggage')
        sleep_dot()

        # This is how you would represent starting work locally.
        with opentracing.start_child_span(parent_span, operation_name='trivial/child_request') as child_span:
            child_span.log_event('Uh Oh!', payload={'error': True})
            child_span.set_tag('span_type', 'child')
            sleep_dot()

            # Play with the propagation APIs... this is not IPC and thus not
            # where they're intended to be used.
            text_carrier = {}
            opentracing.tracer.inject(child_span, opentracing.Format.TEXT_MAP, text_carrier)
            with opentracing.tracer.join(
                    'trivia/remote_span',
                    opentracing.Format.TEXT_MAP,
                    text_carrier) as remote_span:
                remote_span.log_event('Remote!')
                remote_span.set_tag('span_type', 'remote')
                sleep_dot()



def lightstep_tracer_from_args():
    """Initializes lightstep from the commandline args.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--token', help='Your LightStep access token.')
    parser.add_argument('--host', help='The LightStep reporting service host to contact.',
                        default='collector.lightstep.com')
    parser.add_argument('--port', help='The LightStep reporting service port.',
                        type=int, default=443)
    parser.add_argument('--use_tls', help='Whether to use TLS for reporting',
                        type=bool, default=True)
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
    opentracing.tracer = opentracing.Tracer()
    add_spans()

    # Use LightStep's debug tracer, which logs to the console instead of
    # reporting to LightStep.
    opentracing.tracer = lightstep.tracer.init_debug_tracer()
    try:
        add_spans()
    finally:
        opentracing.tracer.flush()

    # Use LightStep's opentracing implementation
    opentracing.tracer = lightstep_tracer_from_args()
    try:
        add_spans()
    finally:
        opentracing.tracer.flush()

    print 'World!'
