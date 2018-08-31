"""Simple example showing several generations of spans in a trace.
"""
import argparse
import contextlib
import sys
import time
import traceback

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
    with opentracing.tracer.start_span(operation_name='trivial/initial_request') as parent_span:
        parent_span.set_tag('url', 'localhost')
        sleep_dot()
        parent_span.log_event('All good here!', payload={'N': 42, 'pi': 3.14, 'abc': 'xyz'})
        parent_span.log_kv({'foo': 'bar', 'int': 42, 'float': 4.2, 'bool': True, 'obj': {'blargh': 'hmm', 'whee': 4324}})
        parent_span.set_tag('span_type', 'parent')
        parent_span.set_tag('int_tag', 5)
        parent_span.set_tag('unicode_val', u'non-ascii: \u200b')
        parent_span.set_tag('bool_tag', True)
        parent_span.set_baggage_item('checked', 'baggage')
        sleep_dot()

        # This is how you would represent starting work locally.
        with opentracing.start_child_span(parent_span, operation_name='trivial/child_request') as child_span:
            child_span.set_tag('span_type', 'child')
            # Pretend there was an error
            child_span.set_tag('error', True)
            child_span.log_event('Uh Oh!', payload={'stacktrace': traceback.extract_stack()})
            sleep_dot()

            # Play with the propagation APIs... this is not IPC and thus not
            # where they're intended to be used.
            text_carrier = {}
            opentracing.tracer.inject(child_span.context, opentracing.Format.TEXT_MAP, text_carrier)

            span_context = opentracing.tracer.extract(opentracing.Format.TEXT_MAP, text_carrier)
            with opentracing.tracer.start_span(
                'trivial/remote_span',
                child_of=span_context) as remote_span:
                    remote_span.log_event('Remote!')
                    remote_span.set_tag('span_type', 'remote')
                    sleep_dot()

def lightstep_tracer_from_args():
    """Initializes lightstep from the commandline args.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--token', help='Your LightStep access token.',
                        default='{your_access_token}')
    parser.add_argument('--host', help='The LightStep reporting service host to contact.',
                        default='collector.lightstep.com')
    parser.add_argument('--port', help='The LightStep reporting service port.',
                        type=int, default=443)
    parser.add_argument('--use_tls', help='Add this argument if you want to use TLS.',
                        action='store_true')
    parser.add_argument('--component_name', help='The LightStep component name',
                        default='TrivialExample')
    args = parser.parse_args()

    return lightstep.Tracer(
            component_name=args.component_name,
            access_token=args.token,
            collector_host=args.host,
            collector_port=args.port,
            verbosity=1,
            collector_encryption=('tls' if args.use_tls else 'none'))


if __name__ == '__main__':
    print('Hello ')

    # Use LightStep's opentracing implementation
    with lightstep_tracer_from_args() as tracer:
        opentracing.tracer = tracer
        add_spans()

    print(' World!')
