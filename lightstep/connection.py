""" Connection class establishes HTTP connection with server.
    Utilized to send Thrift Report Requests.
"""
from thrift import Thrift
from thrift.transport import THttpClient
from thrift.protocol import TBinaryProtocol
from .crouton import ReportingService

class _Connection(object):
    """Instances of _Connection are used to establish a connection to the
    server via HTTP protocol.

    This class is NOT THREADSAFE and access must by synchronized externally.
    """
    def __init__(self, service_url):
        self._service_url = service_url
        self._transport = None
        self._client = None
        self.ready = False
        self._report_exceptions_count = 0

    def open(self):
        """Establish HTTP connection to the server.

        Note: THttpClient also supports https and will use http/https according
        to the scheme in the URL it is given.
        """
        try:
            self._transport = THttpClient.THttpClient(self._service_url)
            self._transport.open()
            protocol = TBinaryProtocol.TBinaryProtocol(self._transport)
            self._client = ReportingService.Client(protocol)
        except Thrift.TException:
            self._report_exceptions_count += 1
        else:
            self.ready = True


    def report(self, *args, **kwargs):
        """Report to the server."""
        # Notice the annoying case change on the method name. I chose to stay
        # consistent with casing in this class vs staying consistent with the
        # casing of the pass-through method.
        return self._client.Report(*args, **kwargs)

    def close(self):
        """Close HTTP connection to the server."""
        if self._transport is None:
            return
        if self._client is None:
            return
        self._transport.close()
