"""Demonstrates a Trace distributed across multiple machines.

A TraceContext's text representation is stored in the headers of an HTTP request.

Runs two threads, starts a Trace in the client and passes the TraceContext to the server.
"""

import argparse
import errno
import socket
import sys
import threading
import urllib2

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

import opentracing
import opentracing.ext.tags

import lightstep.helpers
import lightstep.tracer

class RemoteHandler(BaseHTTPRequestHandler):
    """This handler receives the request from the client.
    """
    def do_GET(self):
        with before_answering_request(self, opentracing.tracer) as server_span:

            server_span.info('Received request for %s', self.path)

            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write("Hello World!")

            server_span.info('Finished preparing response for %s', self.path)


def before_sending_request(request, parent_span):
    """Context manager creates Span and encodes the span's TraceContext into request.
    """
    operation = 'Sending request'
    if parent_span is None:
        span = opentracing.tracer.start_trace(operation_name=operation)
    else:
        span = parent_span.start_child(operation_name=operation)

    span.set_tag('server.http.url', request.get_full_url())
    host = request.get_host()
    if host:
        span.set_tag(opentracing.ext.tags.PEER_HOST_IPV4, host)

    lightstep.helpers.trace_context_writer(span.trace_context,
                                           opentracing.tracer,
                                           add=request.add_header)
    return span


def before_answering_request(handler, tracer):
    """Context manager creates a Span, using TraceContext encoded in handler if possible.
    """
    context = lightstep.helpers.trace_context_from_tuples(handler.headers.items(),
                                                          opentracing.tracer)
    operation = 'Answering request ' + handler.path
    if context is None:
        print 'ERROR: Context missing, starting new trace'
        global _exit_code
        _exit_code = errno.ENOMSG
        span = tracer.start_trace(operation_name=operation)
        headers = ', '.join({k + '=' + v for k, v in handler.headers.items()})
        span.error('Could not extract trace context from http headers: %s', headers)
        print 'Could not extract trace context from http headers: ' + headers
    else:
        print 'Context received, joining remote trace'
        span = tracer.join_trace(operation_name=operation,
                                 parent_trace_context=context)

    host, port = handler.client_address
    if host:
        span.set_tag(opentracing.ext.tags.PEER_HOST_IPV4, host)
    if port:
        span.set_tag(opentracing.ext.tags.PEER_PORT, str(port))

    return span


def pick_unused_port():
    """ Since we don't reserve the port, there's a chance it'll get grabed, but that's unlikely.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    port = s.getsockname()[1]
    s.close()
    return port


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
    opentracing.tracer = lightstep_tracer_from_args()
    global _exit_code
    _exit_code = 0

    #Create a web server and define the handler to manage the
    #incoming request
    port_number = pick_unused_port()
    server = HTTPServer(('', port_number), RemoteHandler)

    try:
        # Run the server in a separate thread.
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.start()
        print 'Started httpserver on port ', port_number

        # Prepare request in the client
        url = 'http://localhost:{}'.format(port_number)
        request = urllib2.Request(url)
        with before_sending_request(request=request,
                                    parent_span=None) as client_span:

            client_span.info('About to send request to %s', url)

            # Send request to server
            response = urllib2.urlopen(request)

            response_body = response.read()
            client_span.info('Server returned %d: %s', response.code, response_body)

        print 'Server returned ' + str(response.code) + ': ' + response_body

        sys.exit(_exit_code)

    finally:
        server.shutdown()
